"""Optional authorized ixigo partner train synchronization state.

Revision ID: 20260822_09
Revises: 20260822_08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260822_09"
down_revision = "20260822_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO data_sources (
            id, key, display_name, category, provider_domain, reference_url,
            terms_note, authority_level, official, free_for_mvp, requires_key,
            default_fresh_seconds, aging_after_seconds, stale_after_seconds,
            enabled, limitations
        ) VALUES (
            '10000000-0000-0000-0000-000000000012',
            'ixigo_partner',
            'ixigo authorized partner gateway',
            'PASSENGER_TRAIN_STATUS',
            'ixigo.com',
            'https://www.ixigo.com/about/terms-of-use/',
            'No public developer API was verified; use only separately authorized partner access.',
            'SUPPLEMENTARY_NON_OFFICIAL_FREIGHT',
            false, false, true, 300, 900, 1800, true,
            '{"passenger_oriented": true, "freight_authority": false, "requires_authorized_contract": true}'::jsonb
        ) ON CONFLICT (key) DO NOTHING
        """
    )
    op.create_table(
        "train_sync_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("train_schedules.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("train_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("freshness", sa.String(30), nullable=False),
        sa.Column("current_station", sa.String(160)),
        sa.Column("station_code", sa.String(20)),
        sa.Column("delay_minutes", sa.Float()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "provenance_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provenance_records.id", ondelete="SET NULL"),
        ),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    for name, columns in (
        ("ix_train_sync_states_user_id", ["user_id"]),
        ("ix_train_sync_states_schedule_id", ["schedule_id"]),
        ("ix_train_sync_states_train_number", ["train_number"]),
        ("ix_train_sync_states_status", ["status"]),
        ("ix_train_sync_states_provenance_record_id", ["provenance_record_id"]),
        ("ix_train_sync_owner_observed", ["user_id", "observed_at"]),
    ):
        op.create_index(name, "train_sync_states", columns)


def downgrade() -> None:
    op.drop_table("train_sync_states")
    op.execute(
        "DELETE FROM data_sources "
        "WHERE id = '10000000-0000-0000-0000-000000000012' "
        "AND key = 'ixigo_partner'"
    )
