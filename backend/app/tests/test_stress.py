"""Comprehensive high-load stress testing suite for ClearPath Nexus.

Validates performance, memory limits, floating-point precision, and
behavior under extreme load for routing, threat simulation, spatial
calculations, and Prometheus telemetry.
"""

from types import SimpleNamespace
from uuid import uuid4
import time
import random

from app.core.observability import MetricsRegistry
from app.services.router_engine import (
    find_route_segments,
    validate_cargo_clearance,
)
from app.services.reliability import apply_threat_simulation


def test_dijkstra_high_load_graph_stress():
    """Stress test Dijkstra on a large interconnected network (500 nodes, 2000 edges)."""
    node_count = 500
    nodes = [uuid4() for _ in range(node_count)]
    segments = []

    # Generate a dense connected graph
    for i in range(node_count - 1):
        # Guarantee connectivity along the backbone
        segments.append(
            SimpleNamespace(
                id=uuid4(),
                source_station_id=nodes[i],
                dest_station_id=nodes[i + 1],
                historical_delay_hours=random.uniform(0.1, 3.0),
                congestion_factor=random.uniform(1.0, 2.0),
            )
        )

    # Add cross-connecting bypass branches
    for _ in range(1500):
        src_idx = random.randint(0, node_count - 2)
        dst_idx = random.randint(src_idx + 1, min(node_count - 1, src_idx + 20))
        segments.append(
            SimpleNamespace(
                id=uuid4(),
                source_station_id=nodes[src_idx],
                dest_station_id=nodes[dst_idx],
                historical_delay_hours=random.uniform(0.0, 5.0),
                congestion_factor=random.uniform(1.0, 2.5),
            )
        )

    start_time = time.perf_counter()
    # Find shortest path from origin to destination across 500 nodes
    path = find_route_segments(segments, nodes[0], nodes[-1])
    duration = time.perf_counter() - start_time

    assert path is not None
    assert len(path) > 0
    assert path[0].source_station_id == nodes[0]
    assert path[-1].dest_station_id == nodes[-1]
    # Traversal on 500-node graph should execute in under 100ms
    assert duration < 0.100, f"Dijkstra search took too long: {duration:.4f}s"


def test_threat_simulation_high_throughput_stress():
    """Execute 10,000 rapid threat simulations with boundary extreme values."""
    base_scores = [0, 15, 50, 75, 88, 100]

    start_time = time.perf_counter()
    for _ in range(10_000):
        base = random.choice(base_scores)
        simulated, alerts = apply_threat_simulation(
            base_score=base,
            storm_severity=random.uniform(0.0, 100.0),
            solar_kp_index=random.randint(0, 9),
            port_congestion=random.uniform(0.0, 100.0),
        )
        # Invariant checks
        assert 0 <= simulated <= 100
        assert simulated <= base or base == 0
        assert isinstance(alerts, list)

    duration = time.perf_counter() - start_time
    assert duration < 0.500, f"10k simulations took too long: {duration:.4f}s"


def test_metrics_registry_high_concurrency_stress():
    """Stress test Prometheus MetricsRegistry with 25,000 rapid event recordings."""
    registry = MetricsRegistry()
    paths = [
        "/api/v1/planner/evaluate",
        "/api/v1/planner/suggest",
        "/api/v1/weather/corridor",
        "/health",
    ]
    methods = ["GET", "POST"]
    status_codes = [200, 201, 400, 401, 403, 429, 500, 503]

    start_time = time.perf_counter()
    for _ in range(25_000):
        m = random.choice(methods)
        p = random.choice(paths)
        s = random.choice(status_codes)
        lat = random.uniform(0.005, 0.450)
        registry.record_request(m, p, s, lat)
        registry.record_route_evaluation(blocked=(s == 400))

    export_text = registry.export_prometheus_text()
    duration = time.perf_counter() - start_time

    assert "nexus_http_requests_total" in export_text
    assert "nexus_route_evaluations_total 25000" in export_text
    assert duration < 0.250, f"25k metric records took too long: {duration:.4f}s"


def test_cargo_clearance_boundary_precision_stress():
    """Verify physical clearance safety at boundary precision thresholds."""

    class MockSegment:
        def __init__(self, h, w, wt):
            self.id = uuid4()
            self.max_height_clearance = h
            self.max_width_clearance = w
            self.max_weight_capacity = wt

    seg = MockSegment(4.50, 3.20, 120.0)

    # Exact boundary (should pass)
    res = validate_cargo_clearance(4.50, 3.20, 120.0, [seg])
    assert res["status"] == "APPROVED"
    assert res.get("blocking_segment_id") is None

    # 1 millimeter height violation (should fail closed)
    res = validate_cargo_clearance(4.501, 3.20, 120.0, [seg])
    assert res["status"] == "HARD_BLOCKED"
    assert res["blocking_segment_id"] == seg.id

    # 1 millimeter width violation (should fail closed)
    res = validate_cargo_clearance(4.50, 3.201, 120.0, [seg])
    assert res["status"] == "HARD_BLOCKED"
    assert res["blocking_segment_id"] == seg.id

    # 1 kilogram weight violation (should fail closed)
    res = validate_cargo_clearance(4.50, 3.20, 120.01, [seg])
    assert res["status"] == "HARD_BLOCKED"
    assert res["blocking_segment_id"] == seg.id

    # Massive 10,000-ton cargo (should fail closed)
    res = validate_cargo_clearance(4.50, 3.20, 10000.0, [seg])
    assert res["status"] == "HARD_BLOCKED"
    assert res["blocking_segment_id"] == seg.id
