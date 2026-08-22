from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Mode = Literal["ROAD", "RAIL", "PORT", "SEA"]
SourceType = Literal[
    "LIVE_PROVIDER",
    "PUBLIC_OPEN_DATA",
    "CACHED_PROVIDER",
    "OPERATOR_INPUT",
    "SEEDED_BASELINE",
    "DERIVED",
    "SIMULATED",
    "UNAVAILABLE",
]
CostSourceType = Literal["VERIFIED_TARIFF", "OPERATOR_INPUT", "UNAVAILABLE"]
ComplianceState = Literal[
    "PASSED", "WARNING", "BLOCKED", "MANUAL_REVIEW", "NOT_ASSESSED"
]


class LegConstraint(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    status: Literal["PASSED", "WARNING", "HARD_BLOCKED", "UNKNOWN"]
    detail: str = Field(min_length=2, max_length=500)


class MultimodalLegInput(BaseModel):
    mode: Mode
    origin: str = Field(min_length=2, max_length=160)
    destination: str = Field(min_length=2, max_length=160)
    distance_km: float = Field(ge=0, le=50000)
    estimated_minutes: int = Field(ge=0, le=525600)
    cost_amount: float | None = Field(default=None, ge=0, le=1_000_000_000)
    cost_source_type: CostSourceType = "UNAVAILABLE"
    risk_score: float | None = Field(default=None, ge=0, le=100)
    risk_source_type: SourceType = "UNAVAILABLE"
    compliance_status: ComplianceState = "NOT_ASSESSED"
    compliance_check_id: UUID | None = None
    source_provider: str | None = Field(default=None, max_length=120)
    source_dataset: str | None = Field(default=None, max_length=160)
    source_reference: str | None = Field(default=None, max_length=500)
    source_observed_at: datetime | None = None
    constraints: list[LegConstraint] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_evidence(self) -> "MultimodalLegInput":
        if self.cost_source_type == "UNAVAILABLE" and self.cost_amount is not None:
            raise ValueError("cost_amount requires VERIFIED_TARIFF or OPERATOR_INPUT")
        if self.cost_source_type != "UNAVAILABLE" and self.cost_amount is None:
            raise ValueError("cost source requires cost_amount")
        if self.risk_source_type == "UNAVAILABLE" and self.risk_score is not None:
            raise ValueError("risk_score requires a declared source type")
        if self.risk_source_type != "UNAVAILABLE" and self.risk_score is None:
            raise ValueError("risk source requires risk_score")
        if self.compliance_status in {"PASSED", "WARNING", "BLOCKED"}:
            if self.compliance_check_id is None:
                raise ValueError(
                    "asserted compliance status requires an owned ComplianceGuard check"
                )
        if self.cost_source_type == "VERIFIED_TARIFF":
            if not all(
                [self.source_provider, self.source_dataset, self.source_reference]
            ):
                raise ValueError(
                    "verified tariff requires provider, dataset, and source reference"
                )
        evidence_sources = {
            "LIVE_PROVIDER",
            "PUBLIC_OPEN_DATA",
            "CACHED_PROVIDER",
            "SEEDED_BASELINE",
            "DERIVED",
            "SIMULATED",
        }
        if self.risk_source_type in evidence_sources:
            if not all(
                [self.source_provider, self.source_dataset, self.source_reference]
            ):
                raise ValueError(
                    "non-operator risk requires provider, dataset, and source reference"
                )
        if self.risk_source_type in {
            "LIVE_PROVIDER",
            "PUBLIC_OPEN_DATA",
            "CACHED_PROVIDER",
        } and self.source_observed_at is None:
            raise ValueError("time-sensitive risk requires an observation timestamp")
        return self


class MultimodalPlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    origin: str = Field(min_length=2, max_length=160)
    destination: str = Field(min_length=2, max_length=160)
    cost_currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    legs: list[MultimodalLegInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_chain(self) -> "MultimodalPlanCreate":
        if self.legs[0].origin.casefold() != self.origin.casefold():
            raise ValueError("first leg must begin at plan origin")
        if self.legs[-1].destination.casefold() != self.destination.casefold():
            raise ValueError("last leg must end at plan destination")
        for previous, current in zip(self.legs, self.legs[1:]):
            if previous.destination.casefold() != current.origin.casefold():
                raise ValueError("multimodal leg chain is discontinuous")
        return self


class MultimodalLegResponse(BaseModel):
    id: UUID
    sequence: int
    mode: str
    origin: str
    destination: str
    distance_km: float
    estimated_minutes: int
    cost_amount: float | None
    cost_source_type: str
    risk_score: float | None
    risk_source_type: str
    compliance_status: str
    freshness_state: str
    compliance_check_id: UUID | None
    constraints: list[dict]
    provenance_record_id: UUID | None


class MultimodalPlanResponse(BaseModel):
    id: UUID
    name: str
    origin: str
    destination: str
    status: str
    recommendation: str
    total_distance_km: float
    total_eta_minutes: int
    total_cost: float | None
    cost_currency: str
    cost_completeness: float
    overall_risk_score: float | None
    compliance_status: str
    traceability_summary: dict
    created_at: datetime
    legs: list[MultimodalLegResponse]
