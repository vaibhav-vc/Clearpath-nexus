from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DelayFeatureInput(BaseModel):
    route_id: UUID | None = None
    shipment_id: UUID | None = None
    route_distance: float = Field(ge=0, le=10000)
    segment_count: int = Field(ge=1, le=1000)
    departure_hour: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    month: int = Field(ge=1, le=12)
    current_delay: float = Field(ge=-240, le=10000)
    journey_progress: float = Field(ge=0, le=1)
    weather_score: float = Field(ge=0, le=100)
    rainfall: float = Field(ge=0, le=1000)
    temperature: float = Field(ge=-80, le=80)
    wind_speed: float = Field(ge=0, le=500)
    visibility: float = Field(ge=0, le=100000)
    corridor_congestion: float = Field(ge=0, le=100)
    station_pressure: float = Field(ge=0, le=100)
    historical_delay: float = Field(ge=0, le=10000)
    schedule_conflicts: int = Field(ge=0, le=100)
    port_pressure: float = Field(ge=0, le=100)
    loading_window_delta: float = Field(ge=-10000, le=10000)
    cargo_weight: float = Field(gt=0, le=100000)


class DelayInferenceResponse(BaseModel):
    prediction_type: str
    operational_prediction_minutes: float
    deterministic_prediction_minutes: float
    ml_prediction_minutes: float | None
    model_name: str
    model_version: str
    model_status: str
    used_for_operational_decision: bool
    fallback_used: bool
    fallback_reason: str | None
    artifact_checksum: str | None
    latency_ms: float
    prediction_id: UUID
    provenance_record_id: UUID
    feature_schema_version: str
    confidence_interval: "PredictionInterval"
    explanation: "PredictionExplanation"


class FeatureContribution(BaseModel):
    factor: str
    contribution_minutes: float
    direction: Literal["INCREASE", "DECREASE", "NEUTRAL"]
    input_value: float | int | None = None
    formula: str


class PredictionExplanation(BaseModel):
    method: Literal["DETERMINISTIC_DECOMPOSITION_V1"]
    target: Literal[
        "OPERATIONAL_PREDICTION", "DETERMINISTIC_BASELINE_ONLY"
    ]
    explained_value_minutes: float
    contributions: list[FeatureContribution]
    limitation: str | None = None


class PredictionInterval(BaseModel):
    available: bool
    lower_minutes: float | None = None
    upper_minutes: float | None = None
    nominal_coverage: float | None = Field(default=None, ge=0, le=1)
    method: str
    calibration_rows: int = Field(ge=0)
    calibration_source_types: dict[str, int] = Field(default_factory=dict)
    reason: str | None = None


class ModelSummary(BaseModel):
    model_name: str
    version: str
    status: str
    production: bool
    algorithm: str
    artifact_checksum: str
    feature_schema_version: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    eligibility: dict[str, Any] = Field(default_factory=dict)


class PredictionOutcomeInput(BaseModel):
    actual_remaining_delay_minutes: float = Field(ge=0, le=10000)
    # This authenticated operator endpoint cannot prove that a label came from
    # a live or curated historical system feed. Trusted import pipelines may
    # still create REAL_LIVE/REAL_HISTORICAL dataset rows directly.
    data_class: Literal["OPERATOR_CONFIRMED"] = "OPERATOR_CONFIRMED"


class DriftReport(BaseModel):
    model_name: str
    model_version: str
    status: Literal["INSUFFICIENT_DATA", "STABLE", "WATCH", "DRIFT_DETECTED"]
    labeled_sample_count: int
    minimum_sample_count: int
    observed_mae_minutes: float | None = None
    observed_bias_minutes: float | None = None
    reference_mae_minutes: float | None = None
    mae_ratio: float | None = None
    window_start: str | None = None
    window_end: str | None = None
    operational_mode_counts: dict[str, int] = Field(default_factory=dict)
    source_line: dict[str, Any]


class RetrainingReadiness(BaseModel):
    model_name: str
    model_version: str
    status: Literal["NOT_READY", "NOT_NEEDED", "READY_FOR_MANUAL_REVIEW"]
    gates: dict[str, bool]
    evidence: dict[str, Any]
    manual_approval_required: Literal[True] = True
    automatic_retraining: Literal[False] = False
    automatic_promotion: Literal[False] = False
    recommended_action: str
    source_line: dict[str, Any]
