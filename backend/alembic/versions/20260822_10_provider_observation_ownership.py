"""Ownership scope for schedule-specific provider observations.

Revision ID: 20260822_10
Revises: 20260822_09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260822_10"
down_revision = "20260822_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_observations", sa.Column("user_id", sa.String(64), nullable=True)
    )
    op.create_index(
        "ix_provider_observations_user_id", "provider_observations", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_observations_user_id", table_name="provider_observations"
    )
    op.drop_column("provider_observations", "user_id")
