from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.observability import metrics_registry
from app.models.ml import MLPrediction
from app.models.provenance import LineageEdge, ProvenanceRecord
from app.schemas.ml import (
    DelayFeatureInput,
    DelayInferenceResponse,
    FeatureContribution,
    PredictionExplanation,
    PredictionInterval,
)

FEATURES = [
    "route_distance", "segment_count", "departure_hour", "day_of_week", "month",
    "current_delay", "journey_progress", "weather_score", "rainfall", "temperature",
    "wind_speed", "visibility", "corridor_congestion", "station_pressure",
    "historical_delay", "schedule_conflicts", "port_pressure", "loading_window_delta",
    "cargo_weight",
]
FEATURE_SCHEMA_VERSION = "delay_features_v1"
REQUIRED_PROMOTION_GATES = frozenset(
    {
        "minimum_real_rows",
        "minimum_coverage_days",
        "minimum_corridors",
        "no_synthetic_test_rows",
        "beats_deterministic_by_10_pct",
        "no_forbidden_feature_leakage",
    }
)


def deterministic_delay(features: dict[str, float]) -> float:
    remaining = max(0.0, 1.0 - features["journey_progress"])
    base = features["current_delay"] + features["historical_delay"] * remaining
    weather = (100.0 - features["weather_score"]) * 0.32
    congestion = features["corridor_congestion"] * 0.28
    port = max(0.0, features["port_pressure"] - 50.0) * 0.18
    conflicts = features["schedule_conflicts"] * 12.0
    cargo = max(0.0, features["cargo_weight"] - 100.0) * 0.08
    return round(max(0.0, base + weather + congestion + port + conflicts + cargo), 2)


def deterministic_explanation(
    features: dict[str, float], *, operational: bool
) -> PredictionExplanation:
    remaining = max(0.0, 1.0 - features["journey_progress"])
    contributions = [
        ("current_delay", features["current_delay"], "current_delay"),
        (
            "historical_delay_remaining",
            features["historical_delay"] * remaining,
            "historical_delay * (1 - journey_progress)",
        ),
        (
            "weather_risk",
            (100.0 - features["weather_score"]) * 0.32,
            "(100 - weather_score) * 0.32",
        ),
        (
            "corridor_congestion",
            features["corridor_congestion"] * 0.28,
            "corridor_congestion * 0.28",
        ),
        (
            "port_pressure",
            max(0.0, features["port_pressure"] - 50.0) * 0.18,
            "max(0, port_pressure - 50) * 0.18",
        ),
        (
            "schedule_conflicts",
            features["schedule_conflicts"] * 12.0,
            "schedule_conflicts * 12",
        ),
        (
            "cargo_weight_over_100",
            max(0.0, features["cargo_weight"] - 100.0) * 0.08,
            "max(0, cargo_weight - 100) * 0.08",
        ),
    ]
    raw_total = sum(value for _, value, _ in contributions)
    if raw_total < 0:
        contributions.append(
            ("non_negative_floor", -raw_total, "max(0, raw_total)")
        )
    contribution_inputs = {
        "current_delay": features["current_delay"],
        "historical_delay_remaining": features["historical_delay"],
        "weather_risk": features["weather_score"],
        "corridor_congestion": features["corridor_congestion"],
        "port_pressure": features["port_pressure"],
        "schedule_conflicts": features["schedule_conflicts"],
        "cargo_weight_over_100": features["cargo_weight"],
    }
    items = [
        FeatureContribution(
            factor=factor,
            contribution_minutes=round(value, 4),
            direction=(
                "INCREASE" if value > 0 else "DECREASE" if value < 0 else "NEUTRAL"
            ),
            input_value=contribution_inputs.get(factor),
            formula=formula,
        )
        for factor, value, formula in contributions
    ]
    return PredictionExplanation(
        method="DETERMINISTIC_DECOMPOSITION_V1",
        target="OPERATIONAL_PREDICTION" if operational else "DETERMINISTIC_BASELINE_ONLY",
        explained_value_minutes=deterministic_delay(features),
        contributions=items,
        limitation=(
            None
            if operational
            else "This exact decomposition explains the deterministic baseline, not the ML model output."
        ),
    )


def empirical_prediction_interval(
    prediction_minutes: float,
    metadata: dict[str, Any],
    *,
    use_ml: bool,
) -> PredictionInterval:
    uncertainty = metadata.get("uncertainty", {})
    try:
        calibration_rows = max(0, int(uncertainty.get("calibration_rows", 0) or 0))
        raw_source_types = uncertainty.get("calibration_source_types", {})
        source_types = (
            {str(key): max(0, int(value)) for key, value in raw_source_types.items()}
            if isinstance(raw_source_types, dict)
            else {}
        )
    except (TypeError, ValueError):
        calibration_rows = 0
        source_types = {}
    trusted = uncertainty.get("trusted_operational_calibration") is True
    radius_key = "ml_absolute_error_p90" if use_ml else "deterministic_absolute_error_p90"
    radius = uncertainty.get(radius_key)
    radius_valid = (
        isinstance(radius, (int, float))
        and not isinstance(radius, bool)
        and math.isfinite(float(radius))
    )
    if not trusted or calibration_rows < 30 or not radius_valid:
        return PredictionInterval(
            available=False,
            method="HELD_OUT_ABSOLUTE_RESIDUAL_QUANTILE",
            calibration_rows=calibration_rows,
            calibration_source_types=source_types,
            reason=(
                "At least 30 held-out, curated REAL_LIVE/REAL_HISTORICAL outcomes "
                "are required; no numerical confidence interval is claimed."
            ),
        )
    radius_value = max(0.0, float(radius))
    return PredictionInterval(
        available=True,
        lower_minutes=round(max(0.0, prediction_minutes - radius_value), 2),
        upper_minutes=round(prediction_minutes + radius_value, 2),
        nominal_coverage=0.90,
        method="HELD_OUT_ABSOLUTE_RESIDUAL_QUANTILE",
        calibration_rows=calibration_rows,
        calibration_source_types=source_types,
    )


class DelayPredictionService:
    def __init__(self, artifact_root: str | Path | None = None) -> None:
        root = Path(artifact_root or settings.MODEL_ARTIFACT_ROOT)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[2] / root
        self.root = root.resolve()
        self._model: Any | None = None
        self._metadata: dict[str, Any] | None = None
        self._load_error: str | None = None

    def _trusted_path(self, raw: str) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = self.root / path
        resolved = path.resolve()
        if self.root != resolved and self.root not in resolved.parents:
            raise ValueError("model artifact is outside configured artifact root")
        return resolved

    def load(self) -> None:
        self._model = None
        self._metadata = None
        self._load_error = None
        production_manifest = self.root / "delay_predictor" / "latest.json"
        candidate_manifest = self.root / "delay_predictor" / "latest_candidate.json"
        manifest = (
            production_manifest
            if production_manifest.exists()
            else candidate_manifest
        )
        if not manifest.exists():
            self._load_error = "no registered model manifest"
            return
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            artifact = self._trusted_path(metadata["artifact_path"])
            checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if checksum != metadata["artifact_checksum"]:
                raise ValueError("artifact checksum mismatch")
            if metadata.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
                raise ValueError("feature schema mismatch")
            if metadata.get("feature_list") != FEATURES:
                raise ValueError("feature list or ordering mismatch")
            self._model = joblib.load(artifact)
            self._metadata = metadata
            # Exercise the complete pandas/scikit-learn prediction path during
            # startup. This moves one-time native imports and estimator setup
            # out of the first operator-facing request while also validating
            # that the registered artifact can actually serve its schema.
            bounds = metadata.get("feature_bounds", {})
            warm_values = [
                (float(bounds[name][0]) + float(bounds[name][1])) / 2.0
                for name in FEATURES
            ]
            self._model.predict(pd.DataFrame([warm_values], columns=FEATURES))
        except Exception as exc:
            self._model = None
            self._metadata = None
            self._load_error = str(exc)

    @property
    def metadata(self) -> dict[str, Any] | None:
        if self._model is None and self._load_error is None:
            self.load()
        return self._metadata

    def predict_raw(self, features: dict[str, float]) -> tuple[float | None, str | None]:
        if self._model is None:
            self.load()
        if self._model is None:
            return None, self._load_error or "model unavailable"
        try:
            bounds = (self._metadata or {}).get("feature_bounds", {})
            outliers = [name for name in FEATURES if name in bounds and not bounds[name][0] <= features[name] <= bounds[name][1]]
            if outliers:
                return None, f"out-of-distribution features: {', '.join(outliers)}"
            vector = pd.DataFrame(
                [[features[name] for name in FEATURES]], columns=FEATURES
            )
            return round(max(0.0, float(self._model.predict(vector)[0])), 2), None
        except Exception as exc:
            return None, f"inference error: {type(exc).__name__}"

    async def predict(self, payload: DelayFeatureInput, user_id: str, db: AsyncSession) -> DelayInferenceResponse:
        started = perf_counter()
        values = payload.model_dump(exclude={"route_id", "shipment_id"})
        deterministic = deterministic_delay(values)
        ml_value, fallback_reason = self.predict_raw(values) if settings.ENABLE_ML_INFERENCE else (None, "ML inference disabled")
        metadata = self._metadata or {}
        model_status = metadata.get("status", "UNAVAILABLE")
        gates = metadata.get("eligibility", {}).get("gates", {})
        production_approved = (
            model_status == "PRODUCTION"
            and metadata.get("production") is True
            and REQUIRED_PROMOTION_GATES.issubset(gates)
            and all(value is True for value in gates.values())
        )
        use_ml = ml_value is not None and production_approved
        if ml_value is not None and not use_ml:
            fallback_reason = (
                f"ML model status is {model_status}; only PRODUCTION models may drive "
                "operational decisions"
                if model_status != "PRODUCTION"
                else "ML production approval evidence is incomplete or failed"
            )
        operational = ml_value if use_ml else deterministic
        explanation = deterministic_explanation(values, operational=not use_ml)
        confidence_interval = empirical_prediction_interval(
            operational, metadata, use_ml=use_ml
        )

        feature_record = ProvenanceRecord(
            user_id=user_id, route_id=payload.route_id, entity_type="ml_feature_vector",
            entity_key=f"delay:{datetime.now(timezone.utc).isoformat()}",
            decision_input_role="DELAY_PREDICTION_FEATURES", canonical_source_type="DERIVED",
            raw_source_state="DERIVED", fetched_at=datetime.now(timezone.utc),
            freshness_state="NOT_APPLICABLE", cache_hit=False, used_in_decision=True,
            excluded_reason=None,
            availability_state="AVAILABLE", completeness=1.0, transform_name="delay_feature_builder",
            transform_version="1.0.0", value_summary=values,
            metadata_json={"feature_schema_version": FEATURE_SCHEMA_VERSION},
        )
        db.add(feature_record)
        await db.flush()
        prediction_record = ProvenanceRecord(
            user_id=user_id, route_id=payload.route_id, entity_type="delay_prediction",
            entity_key=f"delay:{metadata.get('version', 'deterministic')}",
            decision_input_role="PREDICTED_DELAY", canonical_source_type="DERIVED",
            raw_source_state="MODEL_INFERENCE" if use_ml else "DETERMINISTIC_FALLBACK",
            fetched_at=datetime.now(timezone.utc), freshness_state="NOT_APPLICABLE", cache_hit=False,
            used_in_decision=True, excluded_reason=None, availability_state="AVAILABLE",
            completeness=1.0,
            transform_name=(metadata.get("model_name", "delay_predictor") if use_ml else "deterministic_delay"),
            transform_version=(metadata.get("version", "unknown") if use_ml else "1.0.0"),
            checksum=metadata.get("artifact_checksum") if use_ml else None,
            value_summary={
                "operational_minutes": operational,
                "ml_minutes": ml_value,
                "deterministic_minutes": deterministic,
                "confidence_interval": confidence_interval.model_dump(mode="json"),
                "explanation": explanation.model_dump(mode="json"),
            },
            metadata_json={
                "model_status": model_status,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "fallback_reason": fallback_reason,
            },
        )
        db.add(prediction_record)
        await db.flush()
        db.add(LineageEdge(parent_record_id=feature_record.id, child_record_id=prediction_record.id, relationship="TRANSFORMED_INTO"))
        prediction = MLPrediction(
            user_id=user_id, route_id=payload.route_id, shipment_id=payload.shipment_id,
            model_name=metadata.get("model_name", "deterministic_delay"),
            model_version=metadata.get("version", "1.0.0"), model_status=model_status,
            prediction_type="remaining_delay_minutes", predicted_value=operational,
            deterministic_value=deterministic, predicted_at=datetime.now(timezone.utc),
            feature_snapshot=values, provenance_record_id=prediction_record.id, fallback_reason=fallback_reason,
        )
        db.add(prediction)
        await db.commit()
        latency_ms = round((perf_counter() - started) * 1000, 2)
        metrics_registry.record_prediction(
            latency_ms / 1000,
            not use_ml,
            False,
            metadata.get("version", "deterministic") if use_ml else "deterministic",
        )
        return DelayInferenceResponse(
            prediction_type="remaining_delay_minutes", operational_prediction_minutes=operational,
            deterministic_prediction_minutes=deterministic, ml_prediction_minutes=ml_value,
            model_name=prediction.model_name, model_version=prediction.model_version,
            model_status=model_status, used_for_operational_decision=use_ml,
            fallback_used=not use_ml, fallback_reason=fallback_reason,
            artifact_checksum=metadata.get("artifact_checksum"), latency_ms=latency_ms,
            prediction_id=prediction.id, provenance_record_id=prediction_record.id,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            confidence_interval=confidence_interval,
            explanation=explanation,
        )


delay_prediction_service = DelayPredictionService()
