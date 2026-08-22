from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.provenance import _owned_snapshot, component_record_ids
from app.models.provenance import LineageEdge, ProvenanceRecord, RouteDecisionSnapshot

from app.services.provenance import (
    AvailabilityState,
    CanonicalSourceType,
    FreshnessState,
    _record,
    calculate_freshness,
    calculate_traceability_summary,
    capture_route_decision,
    normalize_source_state,
    redact_metadata,
)
from app.services.congestion import CongestionSource
from app.services.port_sync import LoadingWindow, PortDataSource, PortSchedule, compute_port_sync


def test_source_state_normalization_preserves_truth() -> None:
    assert normalize_source_state("LIVE_AIS") is CanonicalSourceType.LIVE_PROVIDER
    assert normalize_source_state("STALE_AIS") is CanonicalSourceType.CACHED_PROVIDER
    assert normalize_source_state("OPERATOR_INPUT") is CanonicalSourceType.OPERATOR_INPUT
    assert normalize_source_state("provider-unavailable") is CanonicalSourceType.UNAVAILABLE


def test_freshness_is_source_specific_and_timestamp_based() -> None:
    now = datetime.now(timezone.utc)
    state, age = calculate_freshness("open_meteo", now - timedelta(minutes=20), now, now)
    assert state is FreshnessState.AGING
    assert age == 1200

    state, age = calculate_freshness("demo_engineering", None, now, now)
    assert state is FreshnessState.NOT_APPLICABLE
    assert age is None


def test_traceability_uses_real_five_input_denominator() -> None:
    snapshot_id = uuid4()
    route_id = uuid4()
    records = []
    for role in ("CLEARANCE_DECISION", "WEATHER", "PORT_ALIGNMENT", "CONGESTION"):
        records.append(
            _record(
                user_id="user-a",
                route_id=route_id,
                snapshot_id=snapshot_id,
                source_key="clearpath_derived",
                entity_type=role,
                entity_key=role.lower(),
                source_type=CanonicalSourceType.DERIVED,
                raw_state="DERIVED",
                value={"state": "recorded"},
                request_id="request-a",
                role=role,
                used=True,
            )
        )
    summary = calculate_traceability_summary(records, snapshot_id)
    assert summary.traceability.traced == 4
    assert summary.traceability.total == 5
    assert summary.traceability.coverage_pct == 80.0


def test_unavailable_input_is_explicitly_traced_and_secret_metadata_is_redacted() -> None:
    snapshot_id = uuid4()
    record = _record(
        user_id="user-a",
        route_id=uuid4(),
        snapshot_id=snapshot_id,
        source_key="open_meteo",
        entity_type="WEATHER_OBSERVATION",
        entity_key="weather",
        source_type=CanonicalSourceType.UNAVAILABLE,
        raw_state="UNAVAILABLE",
        value={"status": "unavailable"},
        request_id="request-a",
        role="WEATHER",
        excluded_reason="provider unavailable",
        availability=AvailabilityState.UNAVAILABLE,
    )
    summary = calculate_traceability_summary([record], snapshot_id)
    assert summary.traceability.traced == 1
    assert summary.source_modes.unavailable == 1
    assert redact_metadata({"Authorization": "Bearer secret", "safe": 1}) == {
        "Authorization": "[REDACTED]",
        "safe": 1,
    }


@pytest.mark.asyncio
async def test_route_evidence_lookup_is_ownership_scoped_and_non_disclosing() -> None:
    class EmptyResult:
        def one_or_none(self):
            return None

    class CapturingSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return EmptyResult()

    db = CapturingSession()
    with pytest.raises(HTTPException) as exc:
        await _owned_snapshot(db, uuid4(), "owner-a")
    assert exc.value.status_code == 404
    assert "generated_routes.user_id" in str(db.statement)
    assert "owner-a" in db.statement.compile().params.values()


def test_component_evidence_includes_all_raw_provider_ancestors() -> None:
    raw_weather = SimpleNamespace(id=uuid4())
    raw_noaa = SimpleNamespace(id=uuid4())
    weather_score = SimpleNamespace(id=uuid4())
    records = [raw_weather, raw_noaa, weather_score]
    edges = [
        SimpleNamespace(parent_record_id=raw_weather.id, child_record_id=weather_score.id),
        SimpleNamespace(parent_record_id=raw_noaa.id, child_record_id=weather_score.id),
    ]
    assert component_record_ids(records, edges, [weather_score]) == [
        raw_weather.id,
        raw_noaa.id,
        weather_score.id,
    ]


@pytest.mark.asyncio
async def test_captured_snapshot_keeps_reproducible_port_and_honest_provider_lineage() -> None:
    now = datetime.now(timezone.utc)

    class Session:
        added = []

        def add(self, value):
            self.added.append(value)

        def add_all(self, values):
            self.added.extend(values)

        async def flush(self):
            return None

    segment = SimpleNamespace(
        id=uuid4(),
        max_height_clearance=6.0,
        max_width_clearance=4.0,
        max_weight_capacity=100.0,
        congestion_factor=1.1,
        historical_delay_hours=0.5,
    )
    port_sync = compute_port_sync(
        17,
        PortSchedule(
            source=PortDataSource.OPERATOR_INPUT,
            vessel_status="OPERATOR_DECLARED",
            window=LoadingWindow(
                start=now + timedelta(hours=10), end=now + timedelta(hours=20)
            ),
        ),
        now=now,
    )
    congestion = SimpleNamespace(
        source=CongestionSource.STATIC_PLUS_LIVE_RAIL_AND_PORT,
        score=70.0,
        static_score=80.0,
        live_rail_score=65.0,
        live_weight=0.6,
        port_congestion_pct=20.0,
        port_penalty=5.0,
        detail={
            "rail_source": "CACHED",
            "rail_observed_at": (now - timedelta(hours=2)).isoformat(),
            "rail_fetched_at": now.isoformat(),
            "stations_live": 3,
            "stations_total": 5,
            "port_source": "STALE_AIS",
            "port_observed_at": (now - timedelta(minutes=20)).isoformat(),
        },
    )
    db = Session()
    await capture_route_decision(
        db,
        route=SimpleNamespace(
            id=uuid4(), source_station_code="NGP", dest_station_code="JNPT"
        ),
        user_id="owner-a",
        request_id="request-a",
        cargo={"height": 4.0, "width": 3.0, "weight": 50.0},
        segments=[segment],
        clearance={"status": "APPROVED", "blocking_segment_id": None},
        weather_data={
            "status": "unavailable",
            "_provenance": {
                "provider": "open_meteo",
                "raw_state": "UNAVAILABLE",
                "fetched_at": now.isoformat(),
            },
        },
        kp_data={
            "status": "unavailable",
            "kp_index": None,
            "alert_level": "UNKNOWN",
            "_provenance": {"raw_state": "UNAVAILABLE", "fetched_at": now.isoformat()},
        },
        weather_score=50.0,
        port_sync=port_sync,
        congestion=congestion,
        historical_score=90.0,
        reliability=68,
        estimated_hours=17,
        applied_weights={"weather": 0.4, "port": 0.3, "congestion": 0.15, "historical": 0.15},
        alerts=[],
    )

    records = [value for value in db.added if isinstance(value, ProvenanceRecord)]
    edges = [value for value in db.added if isinstance(value, LineageEdge)]
    snapshot = next(value for value in db.added if isinstance(value, RouteDecisionSnapshot))
    by_type = {record.entity_type: record for record in records}

    assert by_type["PORT_ALIGNMENT_SCORE"].value_summary["train_arrival_hours"] == 17
    assert by_type["PORT_ALIGNMENT_SCORE"].value_summary["loading_window"]["start"]
    assert by_type["RAIL_CONGESTION_SIGNAL"].raw_source_state == "CACHED"
    assert by_type["AIS_PORT_ACTIVITY"].raw_source_state == "STALE_AIS"
    noaa_edge = next(
        edge
        for edge in edges
        if edge.parent_record_id == by_type["SPACE_WEATHER_OBSERVATION"].id
    )
    assert noaa_edge.relationship == "EXCLUDED_FROM"
    assert snapshot.score_breakdown["port"] == port_sync.score
