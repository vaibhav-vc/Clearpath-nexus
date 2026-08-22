"""Link multimodal compliance claims to owned ComplianceGuard checks.

Revision ID: 20260822_11
Revises: 20260822_10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260822_11"
down_revision = "20260822_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "multimodal_legs",
        sa.Column("compliance_check_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_multimodal_leg_compliance_check",
        "multimodal_legs",
        "compliance_checks",
        ["compliance_check_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_multimodal_legs_compliance_check_id",
        "multimodal_legs",
        ["compliance_check_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_multimodal_legs_compliance_check_id", table_name="multimodal_legs"
    )
    op.drop_constraint(
        "fk_multimodal_leg_compliance_check",
        "multimodal_legs",
        type_="foreignkey",
    )
    op.drop_column("multimodal_legs", "compliance_check_id")
