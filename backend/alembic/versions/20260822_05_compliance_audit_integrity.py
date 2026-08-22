"""Tie documents to checks and preserve append-only override history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260822_05"
down_revision = "20260822_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipment_documents",
        sa.Column("check_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shipment_documents_check_id",
        "shipment_documents",
        "compliance_checks",
        ["check_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_shipment_documents_check_id", "shipment_documents", ["check_id"]
    )

    op.create_table(
        "compliance_override_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_checks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_compliance_override_events_check_id", "compliance_override_events", ["check_id"]
    )
    op.create_index(
        "ix_compliance_override_events_user_id", "compliance_override_events", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("compliance_override_events")
    op.drop_index("ix_shipment_documents_check_id", table_name="shipment_documents")
    op.drop_constraint(
        "fk_shipment_documents_check_id", "shipment_documents", type_="foreignkey"
    )
    op.drop_column("shipment_documents", "check_id")
