from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.route import Base


class MLDataset(Base):
    __tablename__ = "ml_datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    real_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    simulated_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seeded_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    routes_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    corridors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feature_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target: Mapped[str] = mapped_column(String(80), nullable=False)
    source_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    file_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    training_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    training_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ml_datasets.id", ondelete="RESTRICT"), nullable=False
    )
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    feature_list: Mapped[list] = mapped_column(JSONB, nullable=False)
    target: Mapped[str] = mapped_column(String(80), nullable=False)
    training_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    test_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    deterministic_baseline_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(500))
    artifact_checksum: Mapped[str | None] = mapped_column(String(64))
    git_commit: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    promotion_status: Mapped[str] = mapped_column(String(30), nullable=False)


class MLModelVersion(Base):
    __tablename__ = "ml_model_versions"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_ml_model_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    training_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ml_training_runs.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_path: Mapped[str] = mapped_column(String(500), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    production: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        Index(
            "ix_ml_prediction_monitoring",
            "user_id",
            "model_name",
            "model_version",
            "predicted_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_routes.id", ondelete="CASCADE"), index=True
    )
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_status: Mapped[str] = mapped_column(String(30), nullable=False)
    prediction_type: Mapped[str] = mapped_column(String(60), nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    deterministic_value: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feature_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provenance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provenance_records.id", ondelete="SET NULL"), index=True
    )
    actual_value_when_known: Mapped[float | None] = mapped_column(Float)
    error_when_known: Mapped[float | None] = mapped_column(Float)
    fallback_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
