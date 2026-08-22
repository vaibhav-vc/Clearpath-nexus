from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from pydantic import ValidationError

from app.ml_pipeline import (
    CANDIDATE_PARAMETERS,
    FEATURES,
    TARGET,
    candidate_estimators,
    dataset_report,
    promotion_gates,
    simulated_rows,
    train,
    validate_dataset,
)
from app.models.ml import MLPrediction
from app.schemas.ml import DelayFeatureInput
from app.schemas.ml import PredictionOutcomeInput
from app.services.ml_prediction import DelayPredictionService, deterministic_delay
from scripts.build_ml_dataset import corridor_for_prediction


def test_simulated_training_data_is_explicitly_classified() -> None:
    frame = pd.DataFrame(simulated_rows(20))
    report = dataset_report(frame)
    assert report["real_row_count"] == 0
    assert report["simulated_row_count"] == 20


def test_dataset_rejects_missing_feature() -> None:
    frame = pd.DataFrame(simulated_rows(10)).drop(columns=[FEATURES[0]])
    with pytest.raises(ValueError, match="missing columns"):
        validate_dataset(frame)


def test_dataset_rejects_non_finite_values() -> None:
    frame = pd.DataFrame(simulated_rows(10))
    frame.loc[0, FEATURES[0]] = float("inf")
    with pytest.raises(ValueError, match="non-finite"):
        validate_dataset(frame)


def test_dataset_rejects_unknown_source_classification() -> None:
    frame = pd.DataFrame(simulated_rows(10))
    frame.loc[0, "data_class"] = "MYSTERY_LIVE"
    with pytest.raises(ValueError, match="unknown data classes"):
        validate_dataset(frame)


def test_target_is_never_a_model_feature() -> None:
    assert TARGET not in FEATURES
    assert "actual_value_when_known" not in FEATURES


def test_operator_outcome_cannot_claim_trusted_live_classification() -> None:
    with pytest.raises(ValidationError):
        PredictionOutcomeInput(
            actual_remaining_delay_minutes=12,
            data_class="REAL_LIVE",
        )


def test_operator_confirmed_rows_cannot_satisfy_production_evidence_gates() -> None:
    frame = pd.DataFrame(simulated_rows(20))
    frame["data_class"] = "OPERATOR_CONFIRMED"
    report = dataset_report(frame)
    gates = promotion_gates(report, frame["data_class"], improvement=99)

    assert report["real_row_count"] == 0
    assert report["operator_confirmed_row_count"] == 20
    assert gates["minimum_real_rows"] is False
    assert gates["no_synthetic_test_rows"] is False


def test_corridor_identity_requires_same_owner_route_join() -> None:
    route_id = uuid4()
    prediction = SimpleNamespace(
        route_id=route_id,
        user_id="owner-a",
    )
    owned_route = SimpleNamespace(
        id=route_id,
        user_id="owner-a",
        source_station_code="ngp",
        dest_station_code="jnpt",
    )
    other_tenant_route = SimpleNamespace(
        id=route_id,
        user_id="owner-b",
        source_station_code="secret",
        dest_station_code="corridor",
    )

    assert corridor_for_prediction(prediction, owned_route) == "NGP-JNPT"
    assert corridor_for_prediction(prediction, other_tenant_route) == "unassigned"


def test_deterministic_fallback_is_non_negative() -> None:
    features = {name: float(pd.DataFrame(simulated_rows(1)).iloc[0][name]) for name in FEATURES}
    assert deterministic_delay(features) >= 0


def test_cpu_safe_benchmark_has_four_deterministic_candidates() -> None:
    candidates = candidate_estimators()

    assert set(candidates) == {
        "HistGradientBoostingRegressor",
        "RandomForestRegressor",
        "ExtraTreesRegressor",
        "GradientBoostingRegressor",
    }
    assert CANDIDATE_PARAMETERS["RandomForestRegressor"]["n_jobs"] == 1
    assert CANDIDATE_PARAMETERS["ExtraTreesRegressor"]["n_jobs"] == 1


def test_training_registers_simulated_model_as_candidate(tmp_path: Path) -> None:
    metadata = train(
        pd.DataFrame(simulated_rows(90)),
        tmp_path,
        "test",
        source_dataset_checksum="b" * 64,
    )
    assert metadata["status"] == "CANDIDATE"
    assert metadata["production"] is False
    assert metadata["eligibility"]["gates"]["no_synthetic_test_rows"] is False
    assert metadata["uncertainty"]["trusted_operational_calibration"] is False
    assert metadata["metrics"]["candidates_evaluated"] == 4
    assert metadata["metrics"]["test_evaluations"] == 1
    assert metadata["metrics"]["winner_refit_on_train_and_validation"] is True
    assert metadata["metrics"]["split"]["winner_fit_rows"] == (
        metadata["metrics"]["split"]["train_rows"]
        + metadata["metrics"]["split"]["validation_rows"]
    )
    assert set(metadata["metrics"]["validation"]) == set(CANDIDATE_PARAMETERS)
    assert metadata["source_dataset_checksum"] == "b" * 64
    assert len(metadata["benchmark_checksum"]) == 64
    assert len(metadata["metrics_checksum"]) == 64
    assert (
        tmp_path / "delay_predictor" / "test" / "metadata.sha256"
    ).read_text(encoding="utf-8").strip() == metadata["metadata_checksum"]
    assert (tmp_path / "delay_predictor" / "test" / "model.joblib").exists()
    service = DelayPredictionService(tmp_path)
    features = {
        name: float(pd.DataFrame(simulated_rows(1)).iloc[0][name]) for name in FEATURES
    }
    candidate_value, candidate_error = service.predict_raw(features)
    assert candidate_value is not None
    assert candidate_error is None
    assert service.metadata["status"] == "CANDIDATE"


def test_inference_service_falls_back_when_manifest_absent(tmp_path: Path) -> None:
    service = DelayPredictionService(tmp_path)
    features = {name: float(pd.DataFrame(simulated_rows(1)).iloc[0][name]) for name in FEATURES}
    prediction, reason = service.predict_raw(features)
    assert prediction is None
    assert reason == "no registered model manifest"


def test_trusted_model_path_cannot_escape_artifact_root(tmp_path: Path) -> None:
    service = DelayPredictionService(tmp_path)
    with pytest.raises(ValueError, match="outside configured artifact root"):
        service._trusted_path("../untrusted.joblib")


@pytest.mark.asyncio
async def test_candidate_prediction_is_advisory_and_uses_deterministic_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    class FakeDb:
        def __init__(self) -> None:
            self.added = []

        def add(self, item) -> None:
            if hasattr(item, "id") and item.id is None:
                item.id = uuid4()
            self.added.append(item)

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

    service = DelayPredictionService(tmp_path)
    service._metadata = {
        "model_name": "delay_predictor",
        "version": "candidate-1",
        "status": "CANDIDATE",
        "artifact_checksum": "a" * 64,
    }
    monkeypatch.setattr(service, "predict_raw", lambda _features: (1.0, None))
    row = simulated_rows(1)[0]
    payload = DelayFeatureInput(**{name: row[name] for name in FEATURES})
    db = FakeDb()

    result = await service.predict(payload, "owner-a", db)

    stored = next(item for item in db.added if isinstance(item, MLPrediction))
    assert result.used_for_operational_decision is False
    assert result.fallback_used is True
    assert result.operational_prediction_minutes == result.deterministic_prediction_minutes
    assert stored.predicted_value == result.operational_prediction_minutes
    assert "only PRODUCTION models" in (result.fallback_reason or "")
