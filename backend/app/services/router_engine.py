from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, Point

from app.models.route import LineSegment, Station


@dataclass
class SnapResult:
    segment: LineSegment
    fraction: float
    lat: float
    lon: float
    offset_km: float


@dataclass
class ResolvedPosition:
    lat: float
    lon: float
    mode: str
    routing_start_id: UUID
    routing_start_code: str
    snapped_track: str | None
    station_code: str | None
    offset_km: float
    partial_coords: list[list[float]] | None
    current_segment_id: UUID | None
    snap_fraction: float | None


def validate_cargo_clearance(
    cargo_height: float,
    cargo_width: float,
    cargo_weight: float,
    segments: list[LineSegment],
) -> dict[str, Any]:
    """NEXUS-002: Deterministic physical cargo clearance validator."""
    for segment in segments:
        if (
            cargo_height > float(segment.max_height_clearance)
            or cargo_width > float(segment.max_width_clearance)
            or cargo_weight > float(segment.max_weight_capacity)
        ):
            return {
                "status": "HARD_BLOCKED",
                "reliability_score": 0,
                "blocking_segment_id": segment.id,
            }

    return {"status": "APPROVED"}


def calculate_segment_cost(seg: LineSegment) -> float:
    """Calculate multi-criteria impedance weight for a railway track segment."""
    base_hours = 4.5
    delay_hours = float(seg.historical_delay_hours)
    congestion_penalty = max(0.0, float(seg.congestion_factor) - 1.0) * 3.0
    return base_hours + delay_hours * 1.2 + congestion_penalty


def find_route_segments(
    segments: list[LineSegment],
    source_id: UUID,
    dest_id: UUID,
) -> list[LineSegment]:
    """Weighted multi-criteria Dijkstra path finder optimizing speed, congestion, and reliability."""
    if source_id == dest_id:
        return []

    adjacency: dict[UUID, list[LineSegment]] = {}
    for seg in segments:
        adjacency.setdefault(seg.source_station_id, []).append(seg)

    import heapq

    # Priority queue storing (cumulative_cost, node_id, path_segments)
    pq: list[tuple[float, int, UUID, list[LineSegment]]] = []
    counter = 0
    heapq.heappush(pq, (0.0, counter, source_id, []))
    best_cost: dict[UUID, float] = {source_id: 0.0}

    while pq:
        cost, _, current, path = heapq.heappop(pq)

        if current == dest_id:
            return path

        if cost > best_cost.get(current, float("inf")):
            continue

        for seg in adjacency.get(current, []):
            next_id = seg.dest_station_id
            seg_cost = calculate_segment_cost(seg)
            new_cost = cost + seg_cost

            if new_cost < best_cost.get(next_id, float("inf")):
                best_cost[next_id] = new_cost
                counter += 1
                heapq.heappush(pq, (new_cost, counter, next_id, path + [seg]))

    return []


def compute_congestion_score(segments: list[LineSegment]) -> float:
    if not segments:
        return 50.0
    avg_congestion = sum(float(s.congestion_factor) for s in segments) / len(segments)
    return max(0.0, min(100.0, 100.0 - (avg_congestion - 1.0) * 40.0))


def compute_historical_score(segments: list[LineSegment]) -> float:
    if not segments:
        return 75.0
    avg_delay = sum(float(s.historical_delay_hours) for s in segments) / len(segments)
    return max(0.0, min(100.0, 100.0 - avg_delay * 10.0))


def estimate_transit_hours(segments: list[LineSegment]) -> float:
    base = len(segments) * 4.5
    delay = sum(float(s.historical_delay_hours) for s in segments)
    return round(base + delay, 2)


def predict_transit_delay_minutes(
    segments: list[LineSegment],
    congestion_pct: float,
    weather_risk: float,
) -> dict[str, Any]:
    """NEXUS-007: Heuristic delay predictor with fallback."""
    try:
        if not segments:
            return {"delay_minutes": 30, "confidence": "LOW"}

        base_delay = sum(float(s.historical_delay_hours) for s in segments) * 60
        congestion_overhead = congestion_pct * 0.5
        weather_overhead = weather_risk * 0.8
        total = int(base_delay + congestion_overhead + weather_overhead)

        confidence = "HIGH" if weather_risk < 30 and congestion_pct < 40 else "MEDIUM"
        return {"delay_minutes": total, "confidence": confidence}
    except Exception:
        return {"delay_minutes": 45, "confidence": "LOW"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return r * 2 * asin(sqrt(a))


def segment_length_km(coords: list[list[float]]) -> float:
    total = 0.0
    for i in range(1, len(coords)):
        total += haversine_km(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
    return round(total, 1)


def snap_to_nearest_segment(
    lat: float, lon: float, segments: list[LineSegment]
) -> SnapResult | None:
    point = Point(lon, lat)
    best: SnapResult | None = None

    for seg in segments:
        line: LineString = to_shape(seg.geom_path)
        fraction = line.project(point, normalized=True)
        snapped = line.interpolate(fraction, normalized=True)
        offset_km = haversine_km(lat, lon, snapped.y, snapped.x)
        candidate = SnapResult(
            segment=seg,
            fraction=float(fraction),
            lat=float(snapped.y),
            lon=float(snapped.x),
            offset_km=round(offset_km, 2),
        )
        if best is None or candidate.offset_km < best.offset_km:
            best = candidate

    return best


def resolve_train_position(
    mode: str,
    stations: list[Station],
    segments: list[LineSegment],
    station_code: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> ResolvedPosition | None:
    station_by_code = {s.code: s for s in stations}
    if mode == "station":
        if not station_code:
            return None
        station = station_by_code.get(station_code.upper())
        if not station:
            return None
        point = to_shape(station.coordinates)
        return ResolvedPosition(
            lat=point.y,
            lon=point.x,
            mode=mode,
            routing_start_id=station.id,
            routing_start_code=station.code,
            snapped_track=f"{station.code} yard",
            station_code=station.code,
            offset_km=0.0,
            partial_coords=None,
            current_segment_id=None,
            snap_fraction=None,
        )

    if lat is None or lon is None:
        return None

    snap = snap_to_nearest_segment(lat, lon, segments)
    if not snap:
        return None

    seg = snap.segment
    source = seg.source_station
    dest = seg.dest_station

    partial_coords: list[list[float]] | None = None
    if snap.fraction < 0.95:
        end = to_shape(seg.geom_path).coords[-1]
        partial_coords = [[snap.lat, snap.lon], [end[1], end[0]]]

    return ResolvedPosition(
        lat=snap.lat,
        lon=snap.lon,
        mode=mode,
        routing_start_id=dest.id,
        routing_start_code=dest.code,
        snapped_track=f"{source.code}→{dest.code}",
        station_code=None,
        offset_km=snap.offset_km,
        partial_coords=partial_coords,
        current_segment_id=seg.id,
        snap_fraction=snap.fraction,
    )


def find_all_route_segments(
    segments: list[LineSegment],
    source_id: UUID,
    dest_id: UUID,
    max_paths: int = 5,
) -> list[list[LineSegment]]:
    if source_id == dest_id:
        return [[]]

    adjacency: dict[UUID, list[LineSegment]] = {}
    for seg in segments:
        adjacency.setdefault(seg.source_station_id, []).append(seg)

    results: list[list[LineSegment]] = []

    def dfs(current: UUID, path: list[LineSegment], visited: set[UUID]) -> None:
        if len(results) >= max_paths * 2:
            return
        if current == dest_id:
            results.append(list(path))
            return
        for seg in adjacency.get(current, []):
            next_id = seg.dest_station_id
            if next_id in visited:
                continue
            visited.add(next_id)
            path.append(seg)
            dfs(next_id, path, visited)
            path.pop()
            visited.remove(next_id)

    dfs(source_id, [], {source_id})
    results.sort(key=lambda p: sum(calculate_segment_cost(s) for s in p))
    return results[:max_paths]


def build_track_detail(
    seg: LineSegment,
    coords: list[list[float]],
    phase: str,
    cargo_height: float,
    cargo_width: float,
    cargo_weight: float,
    blocking_id: UUID | None,
    snap_fraction: float | None,
    current_segment_id: UUID | None,
) -> dict[str, Any]:
    blocked = (
        cargo_height > float(seg.max_height_clearance)
        or cargo_width > float(seg.max_width_clearance)
        or cargo_weight > float(seg.max_weight_capacity)
    )
    clearance = "HARD_BLOCKED" if blocked else "APPROVED"
    if blocking_id and seg.id == blocking_id:
        clearance = "HARD_BLOCKED"

    progress_pct = None
    if phase == "CURRENT" and seg.id == current_segment_id and snap_fraction is not None:
        progress_pct = round(snap_fraction * 100)

    advisory = None
    if float(seg.congestion_factor) >= 1.5:
        advisory = "High congestion — expect slow orders"
    elif float(seg.historical_delay_hours) >= 1.0:
        advisory = "Historically delayed block"
    elif clearance == "HARD_BLOCKED":
        advisory = "Clearance violation on this tract"

    source = seg.source_station.code
    dest = seg.dest_station.code

    return {
        "id": seg.id,
        "label": f"{source} → {dest}",
        "phase": phase,
        "distance_km": segment_length_km(coords),
        "progress_pct": progress_pct,
        "max_height": float(seg.max_height_clearance),
        "max_width": float(seg.max_width_clearance),
        "max_weight": float(seg.max_weight_capacity),
        "congestion": float(seg.congestion_factor),
        "historical_delay_hours": float(seg.historical_delay_hours),
        "clearance_status": clearance,
        "advisory": advisory,
    }
