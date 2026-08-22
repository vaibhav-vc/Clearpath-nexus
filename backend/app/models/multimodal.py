from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.route import Base


class MultimodalPlan(Base):
    __tablename__ = "multimodal_plans"
    __table_args__ = (
        Index("ix_multimodal_plan_owner_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    origin: Mapped[str] = mapped_column(String(160), nullable=False)
    destination: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    recommendation: Mapped[str] = mapped_column(String(40), nullable=False)
    total_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    total_eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[float | None] = mapped_column(Numeric(14, 2))
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_completeness: Mapped[float] = mapped_column(Float, nullable=False)
    overall_risk_score: Mapped[float | None] = mapped_column(Float)
    compliance_status: Mapped[str] = mapped_column(String(30), nullable=False)
    compliance_check_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_checks.id", ondelete="SET NULL"),
        index=True,
    )
    inputs_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    traceability_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class MultimodalLeg(Base):
    __tablename__ = "multimodal_legs"
    __table_args__ = (
        Index("ix_multimodal_leg_plan_sequence", "plan_id", "sequence", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multimodal_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(160), nullable=False)
    destination: Mapped[str] = mapped_column(String(160), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    cost_source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    compliance_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_provider: Mapped[str | None] = mapped_column(String(120))
    source_dataset: Mapped[str | None] = mapped_column(String(160))
    source_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_state: Mapped[str] = mapped_column(String(30), nullable=False)
    constraints: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    provenance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance_records.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
