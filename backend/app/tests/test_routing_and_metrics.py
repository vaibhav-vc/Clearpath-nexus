from types import SimpleNamespace
from uuid import uuid4

from app.core.observability import MetricsRegistry
from app.main import normalized_metrics_path
from app.services.router_engine import (
    calculate_segment_cost,
    find_all_route_segments,
    find_route_segments,
)


def _make_mock_segment(source_id, dest_id, delay_hours=0.0, congestion_factor=1.0):
    return SimpleNamespace(
        id=uuid4(),
        source_station_id=source_id,
        dest_station_id=dest_id,
        historical_delay_hours=delay_hours,
        congestion_factor=congestion_factor,
    )


def test_calculate_segment_cost():
    seg = _make_mock_segment(uuid4(), uuid4(), delay_hours=2.0, congestion_factor=1.5)
    cost = calculate_segment_cost(seg)
    # base(4.5) + delay(2.0 * 1.2 = 2.4) + congestion((1.5 - 1.0) * 3.0 = 1.5) = 8.4
    assert round(cost, 2) == 8.4


def test_dijkstra_finds_lowest_cost_path():
    a = uuid4()
    b = uuid4()
    c = uuid4()
    d = uuid4()

    # Route 1: A -> B -> D (high delay on B->D)
    seg1 = _make_mock_segment(a, b, delay_hours=0.0, congestion_factor=1.0)
    seg2 = _make_mock_segment(b, d, delay_hours=5.0, congestion_factor=2.0)

    # Route 2: A -> C -> D (smooth path)
    seg3 = _make_mock_segment(a, c, delay_hours=0.2, congestion_factor=1.0)
    seg4 = _make_mock_segment(c, d, delay_hours=0.2, congestion_factor=1.0)

    all_segs = [seg1, seg2, seg3, seg4]

    best_path = find_route_segments(all_segs, a, d)
    assert len(best_path) == 2
    assert best_path[0] == seg3
    assert best_path[1] == seg4


def test_find_all_route_segments_ranked():
    a = uuid4()
    b = uuid4()
    c = uuid4()
    d = uuid4()

    seg1 = _make_mock_segment(a, b, delay_hours=1.0, congestion_factor=1.0)
    seg2 = _make_mock_segment(b, d, delay_hours=1.0, congestion_factor=1.0)

    seg3 = _make_mock_segment(a, c, delay_hours=0.0, congestion_factor=1.0)
    seg4 = _make_mock_segment(c, d, delay_hours=0.0, congestion_factor=1.0)

    all_segs = [seg1, seg2, seg3, seg4]
    paths = find_all_route_segments(all_segs, a, d, max_paths=3)

    assert len(paths) == 2
    # First path must be the cheaper path (A->C->D)
    assert paths[0][0] == seg3
    assert paths[1][0] == seg1


def test_metrics_registry_export():
    registry = MetricsRegistry()
    registry.record_request("POST", "/api/v1/planner/evaluate", 200, 0.125)
    registry.record_route_evaluation(blocked=True)

    text = registry.export_prometheus_text()
    assert "nexus_http_requests_total" in text
    assert 'method="POST"' in text
    assert 'path="/api/v1/planner/evaluate"' in text
    assert "nexus_route_evaluations_total 1" in text
    assert "nexus_clearance_blocks_total 1" in text


def test_metrics_paths_use_templates_and_normalize_unmatched_uuids():
    matched = SimpleNamespace(
        scope={"route": SimpleNamespace(path="/api/v1/provenance/records/{record_id}")},
        url=SimpleNamespace(path="/ignored"),
    )
    assert normalized_metrics_path(matched) == "/api/v1/provenance/records/{record_id}"

    unmatched = SimpleNamespace(
        scope={},
        url=SimpleNamespace(
            path="/api/v1/provenance/records/550e8400-e29b-41d4-a716-446655440000"
        ),
    )
    assert normalized_metrics_path(unmatched) == "/api/v1/provenance/records/{id}"
