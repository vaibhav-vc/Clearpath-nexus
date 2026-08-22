"""Add Supabase ownership, route dispatch, and train schedules."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260821_03"
down_revision = "20260820_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_routes", sa.Column("user_id", sa.String(length=64), nullable=True))
    op.add_column("generated_routes", sa.Column("dispatch_status", sa.String(length=20), nullable=False, server_default="DRAFT"))
    op.add_column("generated_routes", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE generated_routes SET user_id = 'legacy-unassigned' WHERE user_id IS NULL")
    op.alter_column("generated_routes", "user_id", nullable=False)
    op.create_index("ix_generated_routes_user_id", "generated_routes", ["user_id"])
    op.create_index("ix_generated_routes_dispatch_status", "generated_routes", ["dispatch_status"])

    op.create_table(
        "train_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("generated_route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_routes.id"), nullable=True),
        sa.Column("train_code", sa.String(length=20), nullable=False),
        sa.Column("train_name", sa.String(length=100), nullable=False),
        sa.Column("source_station_code", sa.String(length=10), nullable=False),
        sa.Column("dest_station_code", sa.String(length=10), nullable=False),
        sa.Column("scheduled_departure", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_arrival", sa.DateTime(timezone=True), nullable=False),
        sa.Column("berth_window_start", sa.DateTime(timezone=True)),
        sa.Column("berth_window_end", sa.DateTime(timezone=True)),
        sa.Column("schedule_status", sa.String(length=20), nullable=False, server_default="PLANNED"),
        sa.Column("conflict_status", sa.String(length=20), nullable=False, server_default="CLEAR"),
        sa.Column("conflict_reason", sa.String(length=255)),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    for name, columns in (
        ("ix_train_schedules_user_id", ["user_id"]),
        ("ix_train_schedules_generated_route_id", ["generated_route_id"]),
        ("ix_train_schedules_scheduled_departure", ["scheduled_departure"]),
        ("ix_train_schedules_schedule_status", ["schedule_status"]),
    ):
        op.create_index(name, "train_schedules", columns)


def downgrade() -> None:
    op.drop_table("train_schedules")
    op.drop_index("ix_generated_routes_dispatch_status", table_name="generated_routes")
    op.drop_index("ix_generated_routes_user_id", table_name="generated_routes")
    op.drop_column("generated_routes", "dispatched_at")
    op.drop_column("generated_routes", "dispatch_status")
    op.drop_column("generated_routes", "user_id")
