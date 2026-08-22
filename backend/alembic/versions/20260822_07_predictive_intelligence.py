"""Predictive intelligence monitoring index and v5.3 boundary.

Revision ID: 20260822_07
Revises: 20260822_06
"""

from alembic import op

revision = "20260822_07"
down_revision = "20260822_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ml_prediction_monitoring",
        "ml_predictions",
        ["user_id", "model_name", "model_version", "predicted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ml_prediction_monitoring", table_name="ml_predictions")
