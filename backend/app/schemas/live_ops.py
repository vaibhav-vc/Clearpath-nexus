from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

LiveState = Literal[
    "LIVE", "CACHED", "AGING", "STALE", "UNAVAILABLE", "RATE_LIMITED",
    "AUTH_REQUIRED", "INVALID", "OPERATOR_INPUT", "SIMULATED", "OFFLINE_COMPUTED",
]


class ObservationQuality(BaseModel):
    valid: bool
    completeness: float = Field(ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    validation_errors: list[str] = Field(default_factory=list)


class ObservationLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LiveDataEnvelope(BaseModel):
    provider_key: str
    provider_label: str
    provider_version: str
    category: str
    source_type: str
    status: LiveState
    observed_at: datetime | None
    fetched_at: datetime
    age_seconds: int | None
    freshness: str
    cache_hit: bool
    quality: ObservationQuality
    location: ObservationLocation | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    raw_source_state: str
    request_id: str
    attribution: str | None = None
    limitations: list[str] = Field(default_factory=list)


class EventResponse(BaseModel):
    id: UUID
    event_type: str
    severity: str
    state: str
    title: str
    detail: str
    route_id: UUID | None
    shipment_id: UUID | None
    observed_at: datetime
    created_at: datetime
    source_observation_id: UUID | None
    actionable: bool


class EventStateUpdate(BaseModel):
    state: Literal["ACKNOWLEDGED", "RESOLVED", "DISMISSED"]


class ShipmentCreate(BaseModel):
    reference: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_.:/-]+$")
    route_id: UUID | None = None


class ShipmentPositionCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed: float | None = Field(default=None, ge=0, le=500)
    heading: float | None = Field(default=None, ge=0, lt=360)
    accuracy_meters: float | None = Field(default=None, ge=0, le=100000)
    source_type: Literal["OPERATOR_DEVICE", "GPS_DEVICE", "VEHICLE_TELEMATICS", "IOT_GATEWAY", "MANUAL_UPDATE", "SIMULATED"]
    provider: str | None = Field(default=None, max_length=80)
    observed_at: datetime


class TrainSyncResponse(BaseModel):
    schedule_id: UUID
    provider_key: str
    train_number: str
    status: str
    freshness: str
    current_station: str | None
    station_code: str | None
    delay_minutes: float | None
    latitude: float | None
    longitude: float | None
    observed_at: datetime | None
    fetched_at: datetime
    provenance_record_id: UUID | None
    last_error: str | None
    authority_notice: str
