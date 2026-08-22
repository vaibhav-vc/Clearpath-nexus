"""LiveOps observation/event store and production ML registry foundation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260822_06"
down_revision = "20260822_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id", ondelete="SET NULL")),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("observation_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80)),
        sa.Column("entity_id", sa.String(128)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_state", sa.String(30), nullable=False),
        sa.Column("raw_source_state", sa.String(40), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_checksum", sa.String(64), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_error", sa.Text()),
        sa.Column("provenance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provenance_records.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for name, columns in (
        ("ix_provider_observations_provider_id", ["provider_id"]),
        ("ix_provider_observations_provider_key", ["provider_key"]),
        ("ix_provider_observations_observation_type", ["observation_type"]),
        ("ix_provider_observations_entity_type", ["entity_type"]),
        ("ix_provider_observations_entity_id", ["entity_id"]),
        ("ix_provider_observations_observed_at", ["observed_at"]),
        ("ix_provider_observations_freshness_state", ["freshness_state"]),
        ("ix_provider_observations_payload_checksum", ["payload_checksum"]),
        ("ix_provider_observations_provenance_record_id", ["provenance_record_id"]),
        ("ix_provider_observations_created_at", ["created_at"]),
        ("ix_provider_observation_lookup", ["provider_key", "observation_type", "observed_at"]),
    ):
        op.create_index(name, "provider_observations", columns)

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(80), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_routes.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(30), nullable=False, server_default="PLANNED"),
        sa.Column("tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for name, columns in (("ix_shipments_user_id", ["user_id"]), ("ix_shipments_route_id", ["route_id"]), ("ix_shipments_status", ["status"])):
        op.create_index(name, "shipments", columns)

    op.create_table(
        "shipment_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed", sa.Float()),
        sa.Column("heading", sa.Float()),
        sa.Column("accuracy_meters", sa.Float()),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness", sa.String(30), nullable=False),
        sa.Column("provenance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provenance_records.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for name, columns in (
        ("ix_shipment_positions_shipment_id", ["shipment_id"]),
        ("ix_shipment_positions_observed_at", ["observed_at"]),
        ("ix_shipment_positions_provenance_record_id", ["provenance_record_id"]),
        ("ix_shipment_positions_created_at", ["created_at"]),
        ("ix_shipment_position_latest", ["shipment_id", "observed_at"]),
    ):
        op.create_index(name, "shipment_positions", columns)

    op.create_table(
        "operational_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64)),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_routes.id", ondelete="CASCADE")),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("source_observation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provider_observations.id", ondelete="SET NULL")),
        sa.Column("provenance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provenance_records.id", ondelete="SET NULL")),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for name, columns in (
        ("ix_operational_events_user_id", ["user_id"]), ("ix_operational_events_route_id", ["route_id"]),
        ("ix_operational_events_shipment_id", ["shipment_id"]), ("ix_operational_events_event_type", ["event_type"]),
        ("ix_operational_events_severity", ["severity"]), ("ix_operational_events_state", ["state"]),
        ("ix_operational_events_source_observation_id", ["source_observation_id"]),
        ("ix_operational_events_provenance_record_id", ["provenance_record_id"]),
        ("ix_operational_event_feed", ["state", "severity", "created_at"]),
    ):
        op.create_index(name, "operational_events", columns)

    op.create_table(
        "provider_runtime_state",
        sa.Column("provider_key", sa.String(80), primary_key=True),
        sa.Column("current_state", sa.String(20), nullable=False, server_default="CLOSED"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("freshness", sa.String(30), nullable=False, server_default="UNKNOWN"),
        sa.Column("rate_limited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("authentication_state", sa.String(30), nullable=False, server_default="NOT_REQUIRED"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ml_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_version", sa.String(80), nullable=False, unique=True),
        sa.Column("start_time", sa.DateTime(timezone=True)), sa.Column("end_time", sa.DateTime(timezone=True)),
        sa.Column("row_count", sa.Integer(), nullable=False), sa.Column("real_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("simulated_row_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("seeded_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("routes_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("corridors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feature_schema", postgresql.JSONB(), nullable=False), sa.Column("target", sa.String(80), nullable=False),
        sa.Column("source_summary", postgresql.JSONB(), nullable=False), sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("file_reference", sa.String(500), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ml_datasets_dataset_version", "ml_datasets", ["dataset_version"])

    op.create_table(
        "ml_training_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("training_started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("training_finished_at", sa.DateTime(timezone=True)),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ml_datasets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("algorithm", sa.String(100), nullable=False), sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("feature_list", postgresql.JSONB(), nullable=False), sa.Column("target", sa.String(80), nullable=False),
        sa.Column("training_metrics", postgresql.JSONB(), nullable=False), sa.Column("validation_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("test_metrics", postgresql.JSONB(), nullable=False), sa.Column("deterministic_baseline_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("artifact_path", sa.String(500)), sa.Column("artifact_checksum", sa.String(64)),
        sa.Column("git_commit", sa.String(64)), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("promotion_status", sa.String(30), nullable=False),
    )
    op.create_index("ix_ml_training_runs_model_name", "ml_training_runs", ["model_name"])

    op.create_table(
        "ml_model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(40), nullable=False), sa.Column("algorithm", sa.String(100), nullable=False),
        sa.Column("training_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ml_training_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("promoted_at", sa.DateTime(timezone=True)), sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("artifact_checksum", sa.String(64), nullable=False), sa.Column("metadata_path", sa.String(500), nullable=False),
        sa.Column("feature_schema_version", sa.String(40), nullable=False), sa.Column("production", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("model_name", "version", name="uq_ml_model_name_version"),
    )
    op.create_index("ix_ml_model_versions_model_name", "ml_model_versions", ["model_name"])
    op.create_index("ix_ml_model_versions_status", "ml_model_versions", ["status"])

    op.create_table(
        "ml_predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_routes.id", ondelete="CASCADE")),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE")),
        sa.Column("model_name", sa.String(100), nullable=False), sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("model_status", sa.String(30), nullable=False), sa.Column("prediction_type", sa.String(60), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False), sa.Column("deterministic_value", sa.Float(), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("feature_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("provenance_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provenance_records.id", ondelete="SET NULL")),
        sa.Column("actual_value_when_known", sa.Float()), sa.Column("error_when_known", sa.Float()),
        sa.Column("fallback_reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for name, columns in (("ix_ml_predictions_user_id", ["user_id"]), ("ix_ml_predictions_route_id", ["route_id"]), ("ix_ml_predictions_shipment_id", ["shipment_id"]), ("ix_ml_predictions_provenance_record_id", ["provenance_record_id"])):
        op.create_index(name, "ml_predictions", columns)


def downgrade() -> None:
    for table in ("ml_predictions", "ml_model_versions", "ml_training_runs", "ml_datasets", "operational_events", "shipment_positions", "shipments", "provider_runtime_state", "provider_observations"):
        op.drop_table(table)
