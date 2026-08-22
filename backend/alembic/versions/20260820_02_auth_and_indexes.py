"""Add refresh-token sessions and operational indexes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260820_02"
down_revision = "20260819_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_line_segments_source_station_id", "line_segments", ["source_station_id"])
    op.create_index("ix_line_segments_dest_station_id", "line_segments", ["dest_station_id"])
    op.create_index("ix_generated_routes_created_at", "generated_routes", ["created_at"])
    op.create_foreign_key(
        "fk_generated_routes_blocking_segment_id",
        "generated_routes",
        "line_segments",
        ["blocking_segment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_generated_routes_blocking_segment_id", "generated_routes", type_="foreignkey")
    op.drop_index("ix_generated_routes_created_at", table_name="generated_routes")
    op.drop_index("ix_line_segments_dest_station_id", table_name="line_segments")
    op.drop_index("ix_line_segments_source_station_id", table_name="line_segments")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
