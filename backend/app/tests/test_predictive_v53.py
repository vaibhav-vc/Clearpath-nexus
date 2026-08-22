from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ml_pipeline import FEATURES, simulated_rows
from app.services.ml_monitoring import build_drift_report, build_retraining_readiness
from app.services.ml_prediction import (
    deterministic_delay,
    deterministic_explanation,
    empirical_prediction_interval,
)


def _features() -> dict[str, float]:
    row = simulated_rows(1)[0]
    return {name: float(row[name]) for name in FEATURES}


def _prediction(
    index: int,
    *,
    predicted: float,
    actual: float,
    deterministic: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        predicted_value=predicted,
        deterministic_value=predicted if deterministic is None else deterministic,
        actual_value_when_known=actual,
        predicted_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(days=index),
        route_id=f"route-{index % 3}",
        feature_snapshot={"outcome_data_class": "OPERATOR_CONFIRMED"},
    )


def test_deterministic_explanation_is_an_exact_local_decomposition() -> None:
    features = _features()
    explanation = deterministic_explanation(features, operational=True)
    total = sum(item.contribution_minutes for item in explanation.contributions)

    assert explanation.target == "OPERATIONAL_PREDICTION"
    assert total == pytest.approx(deterministic_delay(features), abs=0.01)


def test_deterministic_explanation_discloses_non_negative_floor() -> None:
    features = {name: 0.0 for name in FEATURES}
    features.update(
        {
            "current_delay": -10.0,
            "journey_progress": 1.0,
            "weather_score": 100.0,
            "cargo_weight": 50.0,
        }
    )
    explanation = deterministic_explanation(features, operational=True)

    assert explanation.explained_value_minutes == 0
    assert any(item.factor == "non_negative_floor" for item in explanation.contributions)


def test_interval_requires_real_held_out_calibration() -> None:
    interval = empirical_prediction_interval(
        40,
        {
            "uncertainty": {
                "calibration_rows": 100,
                "calibration_source_types": {"SIMULATED": 100},
                "trusted_operational_calibration": False,
                "deterministic_absolute_error_p90": 8,
            }
        },
        use_ml=False,
    )

    assert interval.available is False
    assert interval.lower_minutes is None
    assert "no numerical confidence interval" in (interval.reason or "")


def test_interval_uses_stored_empirical_residual_quantile() -> None:
    interval = empirical_prediction_interval(
        40,
        {
            "uncertainty": {
                "calibration_rows": 60,
                "calibration_source_types": {"REAL_HISTORICAL": 60},
                "trusted_operational_calibration": True,
                "ml_absolute_error_p90": 7.5,
            }
        },
        use_ml=True,
    )

    assert interval.available is True
    assert interval.lower_minutes == 32.5
    assert interval.upper_minutes == 47.5
    assert interval.nominal_coverage == 0.9


def test_malformed_interval_metadata_fails_closed() -> None:
    interval = empirical_prediction_interval(
        40,
        {
            "uncertainty": {
                "calibration_rows": "not-a-count",
                "calibration_source_types": {"REAL_HISTORICAL": "invalid"},
                "trusted_operational_calibration": True,
                "ml_absolute_error_p90": float("nan"),
            }
        },
        use_ml=True,
    )

    assert interval.available is False
    assert interval.calibration_rows == 0


def test_drift_monitor_requires_minimum_owner_labeled_sample() -> None:
    rows = [_prediction(index, predicted=10, actual=8) for index in range(5)]
    report = build_drift_report(
        rows,
        model_name="delay_predictor",
        model_version="1",
        ml_reference_mae=5,
        deterministic_reference_mae=5,
    )

    assert report.status == "INSUFFICIENT_DATA"
    assert report.labeled_sample_count == 5


def test_drift_monitor_detects_empirical_error_degradation() -> None:
    rows = [_prediction(index, predicted=20, actual=0) for index in range(20)]
    report = build_drift_report(
        rows,
        model_name="delay_predictor",
        model_version="1",
        ml_reference_mae=5,
        deterministic_reference_mae=5,
    )

    assert report.status == "DRIFT_DETECTED"
    assert report.observed_mae_minutes == 20
    assert report.mae_ratio == 4
    assert report.source_line["raw_source_state"] == "OPERATOR_CONFIRMED_OUTCOMES"


def test_retraining_readiness_never_automates_training_or_promotion() -> None:
    rows = [_prediction(index, predicted=20, actual=0) for index in range(100)]
    drift = build_drift_report(
        rows,
        model_name="delay_predictor",
        model_version="1",
        ml_reference_mae=5,
        deterministic_reference_mae=5,
    )
    readiness = build_retraining_readiness(rows, drift)

    assert readiness.status == "READY_FOR_MANUAL_REVIEW"
    assert readiness.manual_approval_required is True
    assert readiness.automatic_retraining is False
    assert readiness.automatic_promotion is False
    assert all(readiness.gates.values())
