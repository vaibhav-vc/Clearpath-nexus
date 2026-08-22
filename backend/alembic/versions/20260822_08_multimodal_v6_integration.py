"""Multimodal planning persistence and v6 integrated operations boundary.

Revision ID: 20260822_08
Revises: 20260822_07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260822_08"
down_revision = "20260822_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "multimodal_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("origin", sa.String(160), nullable=False),
        sa.Column("destination", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("recommendation", sa.String(40), nullable=False),
        sa.Column("total_distance_km", sa.Float(), nullable=False),
        sa.Column("total_eta_minutes", sa.Integer(), nullable=False),
        sa.Column("total_cost", sa.Numeric(14, 2)),
        sa.Column("cost_currency", sa.String(3), nullable=False),
        sa.Column("cost_completeness", sa.Float(), nullable=False),
        sa.Column("overall_risk_score", sa.Float()),
        sa.Column("compliance_status", sa.String(30), nullable=False),
        sa.Column("inputs_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("traceability_summary", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_multimodal_plans_user_id", "multimodal_plans", ["user_id"])
    op.create_index("ix_multimodal_plans_status", "multimodal_plans", ["status"])
    op.create_index(
        "ix_multimodal_plans_created_at", "multimodal_plans", ["created_at"]
    )
    op.create_index(
        "ix_multimodal_plan_owner_created",
        "multimodal_plans",
        ["user_id", "created_at"],
    )

    op.create_table(
        "multimodal_legs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("multimodal_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("origin", sa.String(160), nullable=False),
        sa.Column("destination", sa.String(160), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("cost_amount", sa.Numeric(14, 2)),
        sa.Column("cost_source_type", sa.String(40), nullable=False),
        sa.Column("risk_score", sa.Float()),
        sa.Column("risk_source_type", sa.String(40), nullable=False),
        sa.Column("compliance_status", sa.String(30), nullable=False),
        sa.Column("source_provider", sa.String(120)),
        sa.Column("source_dataset", sa.String(160)),
        sa.Column("source_observed_at", sa.DateTime(timezone=True)),
        sa.Column("freshness_state", sa.String(30), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False),
        sa.Column(
            "provenance_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provenance_records.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_multimodal_legs_plan_id", "multimodal_legs", ["plan_id"])
    op.create_index("ix_multimodal_legs_mode", "multimodal_legs", ["mode"])
    op.create_index(
        "ix_multimodal_legs_provenance_record_id",
        "multimodal_legs",
        ["provenance_record_id"],
    )
    op.create_index(
        "ix_multimodal_leg_plan_sequence",
        "multimodal_legs",
        ["plan_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("multimodal_legs")
    op.drop_table("multimodal_plans")
