from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.route import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_domain: Mapped[str | None] = mapped_column(String(255))
    reference_url: Mapped[str | None] = mapped_column(String(500))
    license_name: Mapped[str | None] = mapped_column(String(120))
    license_url: Mapped[str | None] = mapped_column(String(500))
    attribution_text: Mapped[str | None] = mapped_column(Text)
    terms_note: Mapped[str | None] = mapped_column(Text)
    authority_level: Mapped[str] = mapped_column(String(80), nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    free_for_mvp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_fresh_seconds: Mapped[int | None] = mapped_column(Integer)
    aging_after_seconds: Mapped[int | None] = mapped_column(Integer)
    stale_after_seconds: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    limitations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RouteDecisionSnapshot(Base):
    __tablename__ = "route_decision_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_routes.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    decision_engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    routing_algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(40), nullable=False)
    clearance_engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_code: Mapped[str] = mapped_column(String(10), nullable=False)
    destination_code: Mapped[str] = mapped_column(String(10), nullable=False)
    cargo_request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    route_segment_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    clearance_state: Mapped[str] = mapped_column(String(30), nullable=False)
    blocking_segment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reliability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    score_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    applied_weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    excluded_factors: Mapped[list] = mapped_column(JSONB, nullable=False)
    environmental_alerts: Mapped[list] = mapped_column(JSONB, nullable=False)
    traceability_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    final_response_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_routes.id", ondelete="CASCADE"), index=True
    )
    decision_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_decision_snapshots.id", ondelete="CASCADE"),
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_input_role: Mapped[str | None] = mapped_column(String(60), index=True)
    canonical_source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_source_state: Mapped[str | None] = mapped_column(String(60))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_state: Mapped[str] = mapped_column(String(30), nullable=False)
    freshness_seconds: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_decision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluded_reason: Mapped[str | None] = mapped_column(Text)
    availability_state: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    completeness: Mapped[float | None] = mapped_column(Numeric(5, 4))
    transform_name: Mapped[str | None] = mapped_column(String(120))
    transform_version: Mapped[str | None] = mapped_column(String(40))
    formula_reference: Mapped[str | None] = mapped_column(String(120))
    request_id: Mapped[str | None] = mapped_column(String(64))
    checksum: Mapped[str | None] = mapped_column(String(64))
    value_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        UniqueConstraint(
            "parent_record_id",
            "child_record_id",
            "relationship",
            name="uq_lineage_parent_child_relationship",
        ),
        CheckConstraint("parent_record_id <> child_record_id", name="ck_lineage_no_self_edge"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
