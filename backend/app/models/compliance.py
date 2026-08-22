from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.route import Base


class ComplianceRuleSource(Base):
    __tablename__ = "compliance_rule_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    authority: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_url: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    limitations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ShipmentDocument(Base):
    __tablename__ = "shipment_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_checks.id", ondelete="CASCADE"),
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(60), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(160))
    issuing_authority: Mapped[str | None] = mapped_column(String(255))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checksum: Mapped[str | None] = mapped_column(String(64))
    storage_reference: Mapped[str | None] = mapped_column(String(500))
    verification_state: Mapped[str] = mapped_column(
        String(40), nullable=False, default="UNVERIFIED"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_status: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(40), nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    overridden_by: Mapped[str | None] = mapped_column(String(64))
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplianceCheckItem(Base):
    __tablename__ = "compliance_check_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_checks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_rule_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    penalty_exposure: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplianceOverrideEvent(Base):
    __tablename__ = "compliance_override_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_checks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
