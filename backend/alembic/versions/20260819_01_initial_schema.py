"""Create the ClearPath Nexus operational schema."""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "20260819_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("code", sa.String(length=10), nullable=False, unique=True),
        sa.Column("coordinates", Geometry(geometry_type="POINT", srid=4326), nullable=False),
    )
    op.create_index("ix_stations_coordinates", "stations", ["coordinates"], postgresql_using="gist")
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255)),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "line_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("dest_station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("max_height_clearance", sa.Numeric(4, 2), nullable=False),
        sa.Column("max_width_clearance", sa.Numeric(4, 2), nullable=False),
        sa.Column("max_weight_capacity", sa.Numeric(6, 2), nullable=False),
        sa.Column("congestion_factor", sa.Numeric(3, 2), nullable=False),
        sa.Column("historical_delay_hours", sa.Numeric(4, 2), nullable=False),
        sa.Column("geom_path", Geometry(geometry_type="LINESTRING", srid=4326), nullable=False),
    )
    op.create_index("ix_line_segments_geom_path", "line_segments", ["geom_path"], postgresql_using="gist")
    op.create_table(
        "port_berths",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("port_name", sa.String(length=100), nullable=False),
        sa.Column("berth_identifier", sa.String(length=20), nullable=False),
        sa.Column("vessel_name", sa.String(length=100)),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "generated_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cargo_height_requested", sa.Numeric(4, 2), nullable=False),
        sa.Column("cargo_width_requested", sa.Numeric(4, 2), nullable=False),
        sa.Column("cargo_weight_requested", sa.Numeric(6, 2), nullable=False),
        sa.Column("source_station_code", sa.String(length=10), nullable=False),
        sa.Column("dest_station_code", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reliability_score", sa.Integer(), nullable=False),
        sa.Column("estimated_hours", sa.Numeric(5, 2)),
        sa.Column("blocking_segment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("generated_routes")
    op.drop_table("port_berths")
    op.drop_index("ix_line_segments_geom_path", table_name="line_segments")
    op.drop_table("line_segments")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_stations_coordinates", table_name="stations")
    op.drop_table("stations")
