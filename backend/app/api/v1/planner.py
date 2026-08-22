from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.route import GeneratedRoute, LineSegment, Station, TrainSchedule
from app.schemas.route import (
    AlternateRoute,
    RouteEvaluateRequest,
    RouteEvaluateResponse,
    RouteHistoryResponse,
    RouteDispatchResponse,
    RouteSuggestRequest,
    RouteSuggestResponse,
    ScoreBreakdown,
    SegmentPathResponse,
    StationResponse,
    ThreatSimulationRequest,
    ThreatSimulationResponse,
    TrackSegmentDetail,
    TrainPosition,
)
from app.services.congestion import resolve_congestion
from app.services.port_sync import compute_port_sync, fetch_port_schedule
from app.services.provenance import capture_route_decision
from app.services.reliability import (
    apply_threat_simulation,
    calculate_route_reliability,
    effective_weights,
)
from app.services.router_engine import (
    build_track_detail,
    compute_congestion_score,
    compute_historical_score,
    estimate_transit_hours,
    find_all_route_segments,
    find_route_segments,
    predict_transit_delay_minutes,
    resolve_train_position,
    segment_length_km,
    validate_cargo_clearance,
)
from app.schemas.schedule import TrainScheduleCreate, TrainScheduleResponse, TrainScheduleUpdate
from app.services.scheduling import assess_schedule, ensure_demo_schedules
from app.services.space_weather import space_weather_service

router = APIRouter()


def _route_weather_samples(segments: list[LineSegment]) -> list[tuple[float, float]]:
    """Sample origin, spaced corridor points, and destination with a five-call ceiling."""
    if not segments:
        return []
    total_km = sum(
        segment_length_km([[lat, lon] for lon, lat in to_shape(segment.geom_path).coords])
        for segment in segments
    )
    sample_count = 3 if total_km < 500 else 5
    points: list[tuple[float, float]] = []
    for index in range(sample_count):
        fraction = index / (sample_count - 1)
        segment_index = min(len(segments) - 1, int(fraction * len(segments)))
        local_fraction = (fraction * len(segments)) - segment_index
        if segment_index == len(segments) - 1 and fraction == 1:
            local_fraction = 1.0
        point = to_shape(segments[segment_index].geom_path).interpolate(
            local_fraction, normalized=True
        )
        rounded = (round(point.y, 4), round(point.x, 4))
        if rounded not in points:
            points.append(rounded)
    return points


async def _fetch_sampled_weather_readings(
    segments: list[LineSegment],
) -> tuple[list[tuple[float, float]], list[dict]]:
    coordinates = _route_weather_samples(segments)
    readings = await asyncio.gather(
        *(
            space_weather_service.fetch_route_environmental_risks(lat, lon)
            for lat, lon in coordinates
        )
    )
    return coordinates, readings


def _score_sampled_weather(
    coordinates: list[tuple[float, float]], readings: list[dict], kp_data: dict
) -> tuple[dict, float, list[str]]:
    scored = [space_weather_service.weather_to_score(reading, kp_data) for reading in readings]
    if not scored:
        return {"status": "unavailable", "source": "provider-unavailable"}, 50.0, [
            "Weather sampling unavailable — verify corridor conditions before dispatch"
        ]
    worst_index = min(range(len(scored)), key=lambda index: scored[index][0])
    weather_data = dict(readings[worst_index])
    weather_data["_route_samples"] = [
        {
            "latitude": lat,
            "longitude": lon,
            "score": round(scored[index][0], 1),
            "source_state": reading.get("_provenance", {}).get("raw_source_state", "UNAVAILABLE"),
            "observed_at": reading.get("_provenance", {}).get("observed_at"),
        }
        for index, ((lat, lon), reading) in enumerate(zip(coordinates, readings))
    ]
    alerts = list(dict.fromkeys(alert for _, sample_alerts in scored for alert in sample_alerts))
    # Conservative deterministic aggregation: the weakest sampled point governs the route factor.
    return weather_data, scored[worst_index][0], alerts


@router.get("/stations", response_model=list[StationResponse])
async def list_stations(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[StationResponse]:
    result = await db.execute(select(Station))
    stations = result.scalars().all()
    out: list[StationResponse] = []
    for s in stations:
        point = to_shape(s.coordinates)
        out.append(StationResponse(id=s.id, name=s.name, code=s.code, lat=point.y, lon=point.x))
    return out


@router.post("/evaluate", response_model=RouteEvaluateResponse)
async def evaluate_route(
    payload: RouteEvaluateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RouteEvaluateResponse:
    src_result = await db.execute(
        select(Station).where(Station.code == payload.source_code.upper())
    )
    dst_result = await db.execute(select(Station).where(Station.code == payload.dest_code.upper()))
    source = src_result.scalar_one_or_none()
    dest = dst_result.scalar_one_or_none()

    if not source or not dest:
        raise HTTPException(status_code=404, detail="Source or destination station not found")

    seg_result = await db.execute(
        select(LineSegment).options(
            selectinload(LineSegment.source_station),
            selectinload(LineSegment.dest_station),
        )
    )
    all_segments = list(seg_result.scalars().all())
    route_segments = find_route_segments(all_segments, source.id, dest.id)

    if not route_segments:
        raise HTTPException(status_code=404, detail="No route found between stations")

    clearance = validate_cargo_clearance(
        payload.cargo.height,
        payload.cargo.width,
        payload.cargo.weight,
        route_segments,
    )
    clearance_failed = clearance["status"] == "HARD_BLOCKED"

    kp_data, port_schedule, congestion, sampled_weather = await asyncio.gather(
        space_weather_service.fetch_kp_index(),
        fetch_port_schedule(payload.port_id, payload.vessel_id, payload.operator_loading_window()),
        resolve_congestion(route_segments, dest_code=payload.dest_code),
        _fetch_sampled_weather_readings(route_segments),
    )
    weather_data, weather_score, env_alerts = _score_sampled_weather(
        *sampled_weather, kp_data
    )

    port_sync = compute_port_sync(payload.train_arrival_hours, port_schedule)
    port_score = port_sync.score
    if port_sync.warning:
        env_alerts.append(port_sync.warning)

    congestion_score = congestion.score
    env_alerts.extend(congestion.alerts)
    historical_score = compute_historical_score(route_segments)

    reliability = calculate_route_reliability(
        weather_score,
        port_score,
        congestion_score,
        historical_score,
        clearance_failed,
        port_available=port_sync.available,
    )

    estimated = estimate_transit_hours(route_segments) if not clearance_failed else None
    delay_info = predict_transit_delay_minutes(
        route_segments, 100 - congestion_score, 100 - weather_score
    )
    if delay_info["delay_minutes"] > 60:
        env_alerts.append(
            f"Predicted delay overhead: {delay_info['delay_minutes']} min ({delay_info['confidence']})"
        )

    segment_responses: list[SegmentPathResponse] = []
    for seg in route_segments:
        coords = [[c[1], c[0]] for c in to_shape(seg.geom_path).coords]
        status = (
            "HARD_BLOCKED"
            if clearance_failed and seg.id == clearance.get("blocking_segment_id")
            else clearance["status"]
        )
        segment_responses.append(SegmentPathResponse(id=seg.id, status=status, coordinates=coords))

    record = GeneratedRoute(
        user_id=user.id,
        dispatch_status="DRAFT",
        cargo_height_requested=payload.cargo.height,
        cargo_width_requested=payload.cargo.width,
        cargo_weight_requested=payload.cargo.weight,
        source_station_code=payload.source_code.upper(),
        dest_station_code=payload.dest_code.upper(),
        status=clearance["status"],
        reliability_score=reliability,
        estimated_hours=estimated,
        blocking_segment_id=clearance.get("blocking_segment_id"),
    )
    db.add(record)
    await db.flush()
    applied_weights = effective_weights(port_sync.available)
    provenance_summary = await capture_route_decision(
        db,
        route=record,
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
        cargo=payload.cargo.model_dump(),
        segments=route_segments,
        clearance=clearance,
        weather_data=weather_data,
        kp_data=kp_data,
        weather_score=weather_score,
        port_sync=port_sync,
        congestion=congestion,
        historical_score=historical_score,
        reliability=reliability,
        estimated_hours=estimated,
        applied_weights=applied_weights,
        alerts=env_alerts,
    )
    await db.commit()
    await db.refresh(record)

    return RouteEvaluateResponse(
        route_id=record.id,
        status=clearance["status"],
        reliability_score=reliability,
        blocking_segment_id=clearance.get("blocking_segment_id"),
        estimated_hours=estimated,
        score_breakdown=ScoreBreakdown(
            weather=round(weather_score, 1),
            port=round(port_score, 1),
            congestion=round(congestion_score, 1),
            historical=round(historical_score, 1),
            port_data_source=port_sync.source,
            port_counted=port_sync.available,
            applied_weights=applied_weights,
            congestion_source=congestion.source,
            congestion_static=congestion.static_score,
            congestion_live_rail=congestion.live_rail_score,
            port_congestion_pct=congestion.port_congestion_pct,
        ),
        segments=segment_responses,
        environmental_alerts=env_alerts,
        provenance_summary=provenance_summary,
    )


@router.post("/simulate", response_model=ThreatSimulationResponse)
async def simulate_threat(
    payload: ThreatSimulationRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ThreatSimulationResponse:
    base = 85
    simulated, alerts = apply_threat_simulation(
        base, payload.storm_severity, payload.solar_kp_index, payload.port_congestion
    )
    degradation = round((base - simulated) / base * 100, 1) if base else 0
    return ThreatSimulationResponse(
        original_score=base,
        simulated_score=simulated,
        degradation_pct=degradation,
        alerts=alerts,
    )


@router.post("/suggest", response_model=RouteSuggestResponse)
async def suggest_route_from_position(
    payload: RouteSuggestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RouteSuggestResponse:
    stations_result = await db.execute(select(Station))
    stations = list(stations_result.scalars().all())

    dst_result = await db.execute(
        select(Station).where(Station.code == payload.destination_code.upper())
    )
    dest = dst_result.scalar_one_or_none()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination station not found")

    seg_result = await db.execute(
        select(LineSegment).options(
            selectinload(LineSegment.source_station),
            selectinload(LineSegment.dest_station),
        )
    )
    all_segments = list(seg_result.scalars().all())

    resolved = resolve_train_position(
        payload.location.mode,
        stations,
        all_segments,
        station_code=payload.location.station_code,
        lat=payload.location.lat,
        lon=payload.location.lon,
    )
    if not resolved:
        raise HTTPException(status_code=400, detail="Could not resolve train location on network")

    if resolved.routing_start_id == dest.id:
        raise HTTPException(status_code=400, detail="Train has already reached destination")

    route_segments = find_route_segments(all_segments, resolved.routing_start_id, dest.id)
    if not route_segments and not resolved.partial_coords:
        raise HTTPException(status_code=404, detail="No remaining route to destination")

    full_route: list[tuple[LineSegment, list[list[float]], str]] = []
    if resolved.partial_coords:
        seg = next(s for s in all_segments if s.id == resolved.current_segment_id)
        full_route.append((seg, resolved.partial_coords, "CURRENT"))

    for seg in route_segments:
        if full_route and full_route[0][0].id == seg.id:
            continue
        coords = [[c[1], c[0]] for c in to_shape(seg.geom_path).coords]
        full_route.append((seg, coords, "UPCOMING"))

    if full_route and not resolved.partial_coords:
        seg, coords, _ = full_route[0]
        full_route[0] = (seg, coords, "CURRENT")

    demo_segments = [item[0] for item in full_route]
    clearance = validate_cargo_clearance(
        payload.cargo.height,
        payload.cargo.width,
        payload.cargo.weight,
        demo_segments,
    )
    clearance_failed = clearance["status"] == "HARD_BLOCKED"

    kp_data, port_schedule, congestion, sampled_weather = await asyncio.gather(
        space_weather_service.fetch_kp_index(),
        fetch_port_schedule(payload.port_id, payload.vessel_id, payload.operator_loading_window()),
        resolve_congestion(demo_segments, dest_code=payload.destination_code),
        _fetch_sampled_weather_readings(demo_segments),
    )
    weather_data, weather_score, env_alerts = _score_sampled_weather(
        *sampled_weather, kp_data
    )

    port_sync = compute_port_sync(payload.train_arrival_hours, port_schedule)
    port_score = port_sync.score
    if port_sync.warning:
        env_alerts.append(port_sync.warning)
    if resolved.offset_km > 5:
        env_alerts.append(
            f"Position snapped {resolved.offset_km} km from nearest track — verify GPS lock"
        )

    congestion_score = congestion.score
    env_alerts.extend(congestion.alerts)
    historical_score = compute_historical_score(demo_segments)
    reliability = calculate_route_reliability(
        weather_score,
        port_score,
        congestion_score,
        historical_score,
        clearance_failed,
        port_available=port_sync.available,
    )

    remaining_km = sum(segment_length_km(coords) for _, coords, _ in full_route)
    estimated = (
        round(remaining_km / 45 + sum(float(s.historical_delay_hours) for s in demo_segments), 2)
        if not clearance_failed
        else None
    )

    track_details: list[TrackSegmentDetail] = []
    segment_responses: list[SegmentPathResponse] = []
    for seg, coords, phase in full_route:
        detail = build_track_detail(
            seg,
            coords,
            phase,
            payload.cargo.height,
            payload.cargo.width,
            payload.cargo.weight,
            clearance.get("blocking_segment_id"),
            resolved.snap_fraction,
            resolved.current_segment_id,
        )
        track_details.append(TrackSegmentDetail(**detail))
        status = (
            "HARD_BLOCKED"
            if clearance_failed and seg.id == clearance.get("blocking_segment_id")
            else clearance["status"]
        )
        segment_responses.append(
            SegmentPathResponse(
                id=seg.id,
                status=status,
                coordinates=coords,
                phase=phase,
                label=detail["label"],
            )
        )

    alternates: list[AlternateRoute] = []
    alternate_candidates: list[tuple[list[LineSegment], float, float, float, float]] = []
    for path in find_all_route_segments(all_segments, resolved.routing_start_id, dest.id):
        alt_clearance = validate_cargo_clearance(
            payload.cargo.height,
            payload.cargo.width,
            payload.cargo.weight,
            path,
        )
        if alt_clearance["status"] == "HARD_BLOCKED":
            continue
        alt_congestion = compute_congestion_score(path)
        alt_historical = compute_historical_score(path)

        alt_mid_seg = path[len(path) // 2]
        alt_mid_point = to_shape(alt_mid_seg.geom_path).interpolate(0.5, normalized=True)
        alternate_candidates.append(
            (path, alt_congestion, alt_historical, alt_mid_point.y, alt_mid_point.x)
        )

    alternate_weather = await asyncio.gather(
        *(
            space_weather_service.fetch_route_environmental_risks(lat, lon)
            for _, _, _, lat, lon in alternate_candidates
        )
    )
    for (path, alt_congestion, alt_historical, _, _), alt_weather_data in zip(
        alternate_candidates, alternate_weather, strict=True
    ):
        alt_weather_score, _ = space_weather_service.weather_to_score(alt_weather_data, kp_data)

        alt_reliability = calculate_route_reliability(
            alt_weather_score,
            port_score,
            alt_congestion,
            alt_historical,
            False,
            port_available=port_sync.available,
        )
        label = " → ".join([path[0].source_station.code] + [s.dest_station.code for s in path])
        alternates.append(
            AlternateRoute(
                label=label,
                reliability_score=alt_reliability,
                segment_ids=[s.id for s in path],
                estimated_hours=estimate_transit_hours(path),
                weather_score=alt_weather_score,
            )
        )
    alternates.sort(key=lambda a: a.reliability_score, reverse=True)

    next_station = full_route[0][0].dest_station.code if full_route else None

    record = GeneratedRoute(
        user_id=user.id,
        dispatch_status="DRAFT",
        cargo_height_requested=payload.cargo.height,
        cargo_width_requested=payload.cargo.width,
        cargo_weight_requested=payload.cargo.weight,
        source_station_code=resolved.routing_start_code,
        dest_station_code=payload.destination_code.upper(),
        status=clearance["status"],
        reliability_score=reliability,
        estimated_hours=estimated,
        blocking_segment_id=clearance.get("blocking_segment_id"),
    )
    db.add(record)
    await db.flush()
    applied_weights = effective_weights(port_sync.available)
    provenance_summary = await capture_route_decision(
        db,
        route=record,
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
        cargo=payload.cargo.model_dump(),
        segments=demo_segments,
        clearance=clearance,
        weather_data=weather_data,
        kp_data=kp_data,
        weather_score=weather_score,
        port_sync=port_sync,
        congestion=congestion,
        historical_score=historical_score,
        reliability=reliability,
        estimated_hours=estimated,
        applied_weights=applied_weights,
        alerts=env_alerts,
    )
    await db.commit()
    await db.refresh(record)

    return RouteSuggestResponse(
        route_id=record.id,
        status=clearance["status"],
        reliability_score=reliability,
        blocking_segment_id=clearance.get("blocking_segment_id"),
        estimated_hours=estimated,
        score_breakdown=ScoreBreakdown(
            weather=round(weather_score, 1),
            port=round(port_score, 1),
            congestion=round(congestion_score, 1),
            historical=round(historical_score, 1),
            port_data_source=port_sync.source,
            port_counted=port_sync.available,
            applied_weights=applied_weights,
            congestion_source=congestion.source,
            congestion_static=congestion.static_score,
            congestion_live_rail=congestion.live_rail_score,
            port_congestion_pct=congestion.port_congestion_pct,
        ),
        segments=segment_responses,
        environmental_alerts=env_alerts,
        train_position=TrainPosition(
            lat=resolved.lat,
            lon=resolved.lon,
            mode=payload.location.mode,
            snapped_track=resolved.snapped_track,
            offset_km=resolved.offset_km,
            station_code=resolved.station_code,
        ),
        remaining_km=round(remaining_km, 1),
        eta_hours=estimated,
        track_details=track_details,
        alternate_routes=alternates[:2],
        next_station=next_station,
        provenance_summary=provenance_summary,
    )


@router.get("/routes", response_model=list[RouteHistoryResponse])
async def list_route_history(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[RouteHistoryResponse]:
    result = await db.execute(
        select(GeneratedRoute)
        .where(GeneratedRoute.user_id == user.id)
        .order_by(GeneratedRoute.created_at.desc())
        .limit(100)
    )
    return [RouteHistoryResponse.model_validate(route) for route in result.scalars().all()]


@router.post("/routes/{route_id}/dispatch", response_model=RouteDispatchResponse)
async def dispatch_route(
    route_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RouteDispatchResponse:
    result = await db.execute(
        select(GeneratedRoute).where(
            GeneratedRoute.id == route_id,
            GeneratedRoute.user_id == user.id,
        )
    )
    route = result.scalar_one_or_none()
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    if route.status != "APPROVED":
        raise HTTPException(
            status_code=409, detail="Only clearance-approved routes can be dispatched"
        )
    if route.dispatch_status == "DISPATCHED" and route.dispatched_at:
        return RouteDispatchResponse(
            route_id=route.id,
            dispatch_status=route.dispatch_status,
            dispatched_at=route.dispatched_at,
        )

    route.dispatch_status = "DISPATCHED"
    route.dispatched_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(route)
    return RouteDispatchResponse(
        route_id=route.id,
        dispatch_status=route.dispatch_status,
        dispatched_at=route.dispatched_at,
    )


async def _user_schedule_or_404(db: AsyncSession, schedule_id: UUID, user_id: str) -> TrainSchedule:
    result = await db.execute(
        select(TrainSchedule).where(
            TrainSchedule.id == schedule_id,
            TrainSchedule.user_id == user_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


async def _reassess_schedule(db: AsyncSession, schedule: TrainSchedule) -> None:
    result = await db.execute(
        select(TrainSchedule).where(TrainSchedule.user_id == schedule.user_id)
    )
    others = list(result.scalars().all())
    status, reason = assess_schedule(schedule, others)
    schedule.conflict_status = status
    schedule.conflict_reason = reason
    if schedule.schedule_status not in {"DISPATCHED", "CANCELLED"}:
        schedule.schedule_status = "READY" if status == "CLEAR" else "PLANNED"


@router.get("/schedules", response_model=list[TrainScheduleResponse])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[TrainScheduleResponse]:
    await ensure_demo_schedules(db, user.id)
    result = await db.execute(
        select(TrainSchedule)
        .where(TrainSchedule.user_id == user.id)
        .order_by(TrainSchedule.scheduled_departure.asc())
    )
    return [TrainScheduleResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/schedules/{schedule_id}", response_model=TrainScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TrainScheduleResponse:
    schedule = await _user_schedule_or_404(db, schedule_id, user.id)
    return TrainScheduleResponse.model_validate(schedule)


@router.post("/schedules", response_model=TrainScheduleResponse, status_code=201)
async def create_schedule(
    payload: TrainScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TrainScheduleResponse:
    if payload.generated_route_id:
        route_result = await db.execute(
            select(GeneratedRoute).where(
                GeneratedRoute.id == payload.generated_route_id,
                GeneratedRoute.user_id == user.id,
            )
        )
        if route_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Generated route not found")

    schedule = TrainSchedule(
        user_id=user.id,
        generated_route_id=payload.generated_route_id,
        train_code=payload.train_code.upper(),
        train_name=payload.train_name,
        source_station_code=payload.source_station_code.upper(),
        dest_station_code=payload.dest_station_code.upper(),
        scheduled_departure=payload.scheduled_departure,
        scheduled_arrival=payload.scheduled_arrival,
        berth_window_start=payload.berth_window_start,
        berth_window_end=payload.berth_window_end,
        schedule_status="PLANNED",
        conflict_status="CLEAR",
        is_demo=False,
    )
    db.add(schedule)
    await db.flush()
    await _reassess_schedule(db, schedule)
    await db.commit()
    await db.refresh(schedule)
    return TrainScheduleResponse.model_validate(schedule)


@router.patch("/schedules/{schedule_id}", response_model=TrainScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    payload: TrainScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TrainScheduleResponse:
    schedule = await _user_schedule_or_404(db, schedule_id, user.id)
    if schedule.schedule_status == "DISPATCHED":
        raise HTTPException(status_code=409, detail="Dispatched schedules cannot be edited")

    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(schedule, key, value)

    if schedule.scheduled_arrival <= schedule.scheduled_departure:
        raise HTTPException(
            status_code=422, detail="scheduled_arrival must be after scheduled_departure"
        )
    if (schedule.berth_window_start is None) != (schedule.berth_window_end is None):
        raise HTTPException(
            status_code=422, detail="Both berth window fields are required together"
        )
    if schedule.berth_window_start and schedule.berth_window_end <= schedule.berth_window_start:
        raise HTTPException(
            status_code=422, detail="berth_window_end must be after berth_window_start"
        )

    await _reassess_schedule(db, schedule)
    await db.commit()
    await db.refresh(schedule)
    return TrainScheduleResponse.model_validate(schedule)


@router.post("/schedules/{schedule_id}/dispatch", response_model=TrainScheduleResponse)
async def dispatch_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TrainScheduleResponse:
    schedule = await _user_schedule_or_404(db, schedule_id, user.id)
    if schedule.conflict_status == "BLOCKED":
        raise HTTPException(
            status_code=409, detail=schedule.conflict_reason or "Schedule is blocked"
        )
    if schedule.schedule_status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Cancelled schedules cannot be dispatched")
    if schedule.schedule_status == "DISPATCHED":
        return TrainScheduleResponse.model_validate(schedule)

    if schedule.generated_route_id:
        route_result = await db.execute(
            select(GeneratedRoute).where(
                GeneratedRoute.id == schedule.generated_route_id,
                GeneratedRoute.user_id == user.id,
            )
        )
        route = route_result.scalar_one_or_none()
        if route is None:
            raise HTTPException(status_code=404, detail="Linked route not found")
        if route.status != "APPROVED":
            raise HTTPException(status_code=409, detail="Linked route is not clearance-approved")
        route.dispatch_status = "DISPATCHED"
        route.dispatched_at = datetime.now(timezone.utc)

    schedule.schedule_status = "DISPATCHED"
    schedule.dispatched_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(schedule)
    return TrainScheduleResponse.model_validate(schedule)
