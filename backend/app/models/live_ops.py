from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.route import Base


class ProviderObservation(Base):
    __tablename__ = "provider_observations"
    __table_args__ = (
        Index("ix_provider_observation_lookup", "provider_key", "observation_type", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    observation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    raw_source_state: Mapped[str] = mapped_column(String(40), nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_error: Mapped[str | None] = mapped_column(Text)
    provenance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provenance_records.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(80), nullable=False)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_routes.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PLANNED", index=True)
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShipmentPosition(Base):
    __tablename__ = "shipment_positions"
    __table_args__ = (Index("ix_shipment_position_latest", "shipment_id", "observed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    accuracy_meters: Mapped[float | None] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness: Mapped[str] = mapped_column(String(30), nullable=False)
    provenance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provenance_records.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    __table_args__ = (Index("ix_operational_event_feed", "state", "severity", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_routes.id", ondelete="CASCADE"), index=True
    )
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_observations.id", ondelete="SET NULL"), index=True
    )
    provenance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provenance_records.id", ondelete="SET NULL"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderRuntimeState(Base):
    __tablename__ = "provider_runtime_state"

    provider_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    current_state: Mapped[str] = mapped_column(String(20), nullable=False, default="CLOSED")
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    freshness: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    rate_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authentication_state: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_REQUIRED")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TrainSyncState(Base):
    __tablename__ = "train_sync_states"
    __table_args__ = (
        Index("ix_train_sync_owner_observed", "user_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("train_schedules.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False)
    train_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    freshness: Mapped[str] = mapped_column(String(30), nullable=False)
    current_station: Mapped[str | None] = mapped_column(String(160))
    station_code: Mapped[str | None] = mapped_column(String(20))
    delay_minutes: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provenance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance_records.id", ondelete="SET NULL"),
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
