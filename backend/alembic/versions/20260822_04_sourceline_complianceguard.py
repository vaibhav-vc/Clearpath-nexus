"""Add SourceLine evidence and ComplianceGuard decision-support records."""

from datetime import datetime, timezone
import hashlib
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260822_04"
down_revision = "20260821_03"
branch_labels = None
depends_on = None

JSON_EMPTY = sa.text("'{}'::jsonb")
JSON_LIST = sa.text("'[]'::jsonb")


def _sql_literal(value: object, *, jsonb: bool = False) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if jsonb:
        encoded = json.dumps(value, sort_keys=True).replace("'", "''")
        return f"'{encoded}'::jsonb"
    encoded = str(value).replace("'", "''")
    return f"'{encoded}'"


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("provider_domain", sa.String(255)),
        sa.Column("reference_url", sa.String(500)),
        sa.Column("license_name", sa.String(120)),
        sa.Column("license_url", sa.String(500)),
        sa.Column("attribution_text", sa.Text()),
        sa.Column("terms_note", sa.Text()),
        sa.Column("authority_level", sa.String(80), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("free_for_mvp", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_key", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_fresh_seconds", sa.Integer()),
        sa.Column("aging_after_seconds", sa.Integer()),
        sa.Column("stale_after_seconds", sa.Integer()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=JSON_EMPTY),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_data_sources_key", "data_sources", ["key"], unique=True)

    op.create_table(
        "route_decision_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("decision_engine_version", sa.String(40), nullable=False),
        sa.Column("routing_algorithm_version", sa.String(40), nullable=False),
        sa.Column("scoring_version", sa.String(40), nullable=False),
        sa.Column("clearance_engine_version", sa.String(40), nullable=False),
        sa.Column("source_code", sa.String(10), nullable=False),
        sa.Column("destination_code", sa.String(10), nullable=False),
        sa.Column("cargo_request", postgresql.JSONB(), nullable=False),
        sa.Column("route_segment_ids", postgresql.JSONB(), nullable=False),
        sa.Column("clearance_state", sa.String(30), nullable=False),
        sa.Column("blocking_segment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reliability_score", sa.Integer(), nullable=False),
        sa.Column("estimated_hours", sa.Numeric(8, 2)),
        sa.Column("score_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("applied_weights", postgresql.JSONB(), nullable=False),
        sa.Column("excluded_factors", postgresql.JSONB(), nullable=False, server_default=JSON_LIST),
        sa.Column(
            "environmental_alerts", postgresql.JSONB(), nullable=False, server_default=JSON_LIST
        ),
        sa.Column("traceability_summary", postgresql.JSONB(), nullable=False),
        sa.Column("final_response_summary", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_route_decision_snapshots_route_id",
        "route_decision_snapshots",
        ["route_id"],
        unique=True,
    )
    op.create_index("ix_route_decision_snapshots_user_id", "route_decision_snapshots", ["user_id"])

    op.create_table(
        "provenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_routes.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "decision_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("route_decision_snapshots.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_key", sa.String(255), nullable=False),
        sa.Column("decision_input_role", sa.String(60)),
        sa.Column("canonical_source_type", sa.String(40), nullable=False),
        sa.Column("raw_source_state", sa.String(60)),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("freshness_state", sa.String(30), nullable=False),
        sa.Column("freshness_seconds", sa.Integer()),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("used_in_decision", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("excluded_reason", sa.Text()),
        sa.Column("availability_state", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("completeness", sa.Numeric(5, 4)),
        sa.Column("transform_name", sa.String(120)),
        sa.Column("transform_version", sa.String(40)),
        sa.Column("formula_reference", sa.String(120)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("checksum", sa.String(64)),
        sa.Column("value_summary", postgresql.JSONB(), nullable=False, server_default=JSON_EMPTY),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=JSON_EMPTY),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    for name, columns in (
        ("ix_provenance_records_user_id", ["user_id"]),
        ("ix_provenance_records_route_id", ["route_id"]),
        ("ix_provenance_records_decision_snapshot_id", ["decision_snapshot_id"]),
        ("ix_provenance_records_source_id", ["source_id"]),
        ("ix_provenance_records_entity_type", ["entity_type"]),
        ("ix_provenance_records_decision_input_role", ["decision_input_role"]),
        ("ix_provenance_records_fetched_at", ["fetched_at"]),
    ):
        op.create_index(name, "provenance_records", columns)

    op.create_table(
        "lineage_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "parent_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provenance_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provenance_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("parent_record_id <> child_record_id", name="ck_lineage_no_self_edge"),
        sa.UniqueConstraint(
            "parent_record_id",
            "child_record_id",
            "relationship",
            name="uq_lineage_parent_child_relationship",
        ),
    )
    op.create_index("ix_lineage_edges_parent_record_id", "lineage_edges", ["parent_record_id"])
    op.create_index("ix_lineage_edges_child_record_id", "lineage_edges", ["child_record_id"])

    op.create_table(
        "compliance_rule_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("authority", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(100), nullable=False),
        sa.Column("reference_url", sa.String(500)),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=JSON_EMPTY),
    )
    op.create_table(
        "shipment_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("document_number", sa.String(160)),
        sa.Column("issuing_authority", sa.String(255)),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("checksum", sa.String(64)),
        sa.Column("storage_reference", sa.String(500)),
        sa.Column("verification_state", sa.String(40), nullable=False, server_default="UNVERIFIED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_shipment_documents_user_id", "shipment_documents", ["user_id"])
    op.create_index("ix_shipment_documents_route_id", "shipment_documents", ["route_id"])

    op.create_table(
        "compliance_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generated_routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_status", sa.String(40), nullable=False),
        sa.Column("rule_pack_version", sa.String(40), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("input_summary", postgresql.JSONB(), nullable=False, server_default=JSON_EMPTY),
        sa.Column("overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.Text()),
        sa.Column("overridden_by", sa.String(64)),
        sa.Column("overridden_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_compliance_checks_user_id", "compliance_checks", ["user_id"])
    op.create_index("ix_compliance_checks_route_id", "compliance_checks", ["route_id"])
    op.create_table(
        "compliance_check_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_checks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rule_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_rule_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rule_key", sa.String(100), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("penalty_exposure", sa.Text()),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=JSON_EMPTY),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_compliance_check_items_check_id", "compliance_check_items", ["check_id"])

    now = datetime.now(timezone.utc)
    source_rows = [
        (
            "10000000-0000-0000-0000-000000000001",
            "open_meteo",
            "Open-Meteo",
            "weather",
            "open-meteo.com",
            "https://open-meteo.com/",
            "CC BY 4.0",
            "PUBLIC_DATA_ADAPTER",
            False,
            True,
            False,
            900,
            1800,
            3600,
            {"note": "Hosted service has limits/no SLA; weather is not rail authority."},
        ),
        (
            "10000000-0000-0000-0000-000000000002",
            "openweather",
            "OpenWeather",
            "weather",
            "openweathermap.org",
            "https://openweathermap.org/",
            None,
            "THIRD_PARTY_PROVIDER",
            False,
            False,
            True,
            900,
            1800,
            3600,
            {"note": "Optional keyed weather adapter."},
        ),
        (
            "10000000-0000-0000-0000-000000000003",
            "noaa_swpc",
            "NOAA SWPC",
            "space_weather",
            "noaa.gov",
            "https://www.swpc.noaa.gov/",
            "US Government public data",
            "GOVERNMENT_PUBLIC_SOURCE",
            True,
            True,
            False,
            900,
            1800,
            3600,
            {"note": "Supplemental telemetry risk information; not signalling authority."},
        ),
        (
            "10000000-0000-0000-0000-000000000004",
            "operator_input",
            "Operator Input",
            "human_input",
            None,
            None,
            None,
            "HUMAN_DECLARATION",
            False,
            True,
            False,
            None,
            None,
            None,
            {"note": "Must be verified by qualified personnel."},
        ),
        (
            "10000000-0000-0000-0000-000000000005",
            "demo_engineering",
            "Demo Engineering Constraints",
            "engineering",
            None,
            None,
            None,
            "SEEDED_DEMONSTRATION",
            False,
            True,
            False,
            None,
            None,
            None,
            {"note": "Not certified bridge, OHE, axle-load, or structure-gauge data."},
        ),
        (
            "10000000-0000-0000-0000-000000000006",
            "route_baseline",
            "Seeded Route Baseline",
            "operations_baseline",
            None,
            None,
            None,
            "SEEDED_DEMONSTRATION",
            False,
            True,
            False,
            None,
            None,
            None,
            {"note": "Static congestion and historical-delay demo values."},
        ),
        (
            "10000000-0000-0000-0000-000000000007",
            "railradar",
            "RailRadar",
            "rail_telemetry",
            "railradar.in",
            "https://railradar.in/",
            None,
            "SECONDARY_NON_OFFICIAL",
            False,
            True,
            True,
            7200,
            10800,
            21600,
            {"note": "Passenger-oriented supplementary telemetry; not official freight control."},
        ),
        (
            "10000000-0000-0000-0000-000000000008",
            "aisstream",
            "AISstream",
            "maritime_activity",
            "aisstream.io",
            "https://aisstream.io/",
            None,
            "SECONDARY_BETA",
            False,
            True,
            True,
            300,
            600,
            1200,
            {"note": "AIS activity is not a berth loading schedule."},
        ),
        (
            "10000000-0000-0000-0000-000000000009",
            "maritime_feed",
            "Configured Maritime Berth Feed",
            "port_schedule",
            None,
            None,
            None,
            "CONFIGURATION_DEPENDENT",
            False,
            False,
            True,
            900,
            1800,
            3600,
            {"note": "Authority depends on the configured provider."},
        ),
        (
            "10000000-0000-0000-0000-000000000010",
            "clearpath_derived",
            "ClearPath Deterministic Engine",
            "derived",
            None,
            None,
            "Project source licence",
            "DETERMINISTIC_SOFTWARE",
            False,
            True,
            False,
            None,
            None,
            None,
            {"note": "Derived values are explainable calculations, not source observations."},
        ),
        (
            "10000000-0000-0000-0000-000000000011",
            "openstreetmap",
            "OpenStreetMap",
            "rail_geometry",
            "openstreetmap.org",
            "https://www.openstreetmap.org/copyright",
            "ODbL 1.0",
            "PUBLIC_OPEN_GEODATA",
            False,
            True,
            False,
            None,
            None,
            None,
            {
                "note": "Geometry only; does not certify clearance, structure gauge, or axle load."
            },
        ),
    ]
    for row in source_rows:
        values = [
            *(_sql_literal(item) for item in row[:-1]),
            _sql_literal(row[-1], jsonb=True),
            _sql_literal(now),
            _sql_literal(now),
        ]
        op.execute(
            "INSERT INTO data_sources "
            "(id, key, display_name, category, provider_domain, reference_url, "
            "license_name, authority_level, official, free_for_mvp, requires_key, "
            "default_fresh_seconds, aging_after_seconds, stale_after_seconds, limitations, "
            "created_at, updated_at) VALUES (" + ", ".join(values) + ")"
        )

    rule_text = "ClearPath internal pre-dispatch completeness and expiry policy v1"
    rule_values = [
        _sql_literal("20000000-0000-0000-0000-000000000001"),
        _sql_literal("clearpath_internal_policy"),
        _sql_literal("Pre-dispatch evidence policy"),
        _sql_literal("ClearPath internal decision-support policy"),
        _sql_literal("Operator-defined"),
        _sql_literal("1.0.0"),
        _sql_literal(False),
        _sql_literal(now),
        _sql_literal(hashlib.sha256(rule_text.encode()).hexdigest()),
        _sql_literal(
            {"note": "Not law; requires competent authority and human review."}, jsonb=True
        ),
    ]
    op.execute(
        "INSERT INTO compliance_rule_sources "
        "(id, key, title, authority, jurisdiction, version, official, retrieved_at, "
        "checksum, limitations) VALUES (" + ", ".join(rule_values) + ")"
    )


def downgrade() -> None:
    op.drop_table("compliance_check_items")
    op.drop_table("compliance_checks")
    op.drop_table("shipment_documents")
    op.drop_table("compliance_rule_sources")
    op.drop_table("lineage_edges")
    op.drop_table("provenance_records")
    op.drop_table("route_decision_snapshots")
    op.drop_table("data_sources")
