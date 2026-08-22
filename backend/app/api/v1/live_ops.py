from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.core.security import CurrentUser, get_current_user
from app.models.live_ops import (
    OperationalEvent,
    ProviderObservation,
    ProviderRuntimeState,
    Shipment,
    ShipmentPosition,
    TrainSyncState,
)
from app.models.provenance import ProvenanceRecord
from app.models.route import GeneratedRoute, TrainSchedule
from app.schemas.live_ops import (
    EventResponse,
    EventStateUpdate,
    ShipmentCreate,
    ShipmentPositionCreate,
    TrainSyncResponse,
)
from app.services.ixigo_sync import synchronize_schedule

router = APIRouter()


def train_sync_response(state: TrainSyncState) -> TrainSyncResponse:
    return TrainSyncResponse(
        schedule_id=state.schedule_id,
        provider_key=state.provider_key,
        train_number=state.train_number,
        status=state.status,
        freshness=state.freshness,
        current_station=state.current_station,
        station_code=state.station_code,
        delay_minutes=state.delay_minutes,
        latitude=state.latitude,
        longitude=state.longitude,
        observed_at=state.observed_at,
        fetched_at=state.fetched_at,
        provenance_record_id=state.provenance_record_id,
        last_error=state.last_error,
        authority_notice=(
            "Supplementary passenger information only; not freight operations, "
            "signalling, or official dispatch control."
        ),
    )


def event_response(event: OperationalEvent) -> EventResponse:
    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        severity=event.severity,
        state=event.state,
        title=event.title,
        detail=event.detail,
        route_id=event.route_id,
        shipment_id=event.shipment_id,
        observed_at=event.observed_at,
        created_at=event.created_at,
        source_observation_id=event.source_observation_id,
        actionable=event.user_id is not None,
    )


@router.get("/observations")
async def latest_observations(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    rows = (
        await db.scalars(
            select(ProviderObservation)
            .where(
                or_(
                    ProviderObservation.user_id.is_(None),
                    ProviderObservation.user_id == user.id,
                )
            )
            .order_by(desc(ProviderObservation.fetched_at))
            .limit(limit)
        )
    ).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "provider_key": row.provider_key,
                "observation_type": row.observation_type,
                "entity_id": row.entity_id,
                "status": row.raw_source_state,
                "freshness": row.freshness_state,
                "observed_at": row.observed_at,
                "fetched_at": row.fetched_at,
                "valid": row.valid,
                "data": row.normalized_payload.get("data", {}),
            }
            for row in rows
        ]
    }


@router.get("/provider-health")
async def provider_health(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> dict:
    rows = (
        await db.scalars(
            select(ProviderRuntimeState).order_by(ProviderRuntimeState.provider_key)
        )
    ).all()
    return {
        "items": [
            {
                "provider_key": row.provider_key,
                "circuit_state": row.current_state,
                "consecutive_failures": row.consecutive_failures,
                "last_success_at": row.last_success_at,
                "last_failure_at": row.last_failure_at,
                "latency_ms": row.latency_ms,
                "freshness": row.freshness,
                "rate_limited": row.rate_limited,
                "authentication_state": row.authentication_state,
            }
            for row in rows
        ]
    }


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    state: str | None = Query(
        default=None, pattern=r"^(OPEN|ACKNOWLEDGED|RESOLVED|DISMISSED)$"
    ),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[EventResponse]:
    stmt = select(OperationalEvent).where(
        or_(OperationalEvent.user_id.is_(None), OperationalEvent.user_id == user.id)
    )
    if state:
        stmt = stmt.where(OperationalEvent.state == state)
    rows = (
        await db.scalars(stmt.order_by(desc(OperationalEvent.created_at)).limit(limit))
    ).all()
    return [event_response(row) for row in rows]


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    payload: EventStateUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EventResponse:
    event = await db.scalar(
        select(OperationalEvent).where(
            OperationalEvent.id == event_id,
            OperationalEvent.user_id == user.id,
        )
    )
    if event is None:
        raise HTTPException(404, "Event not found")
    now = datetime.now(timezone.utc)
    event.state = payload.state
    if payload.state == "ACKNOWLEDGED":
        event.acknowledged_at = now
    elif payload.state == "RESOLVED":
        event.resolved_at = now
    await db.commit()
    await db.refresh(event)
    return event_response(event)


@router.get("/events/stream")
async def event_stream(user: CurrentUser = Depends(get_current_user)) -> StreamingResponse:
    async def generate():
        last_id: uuid.UUID | None = None
        for _ in range(120):
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(OperationalEvent)
                    .where(
                        or_(
                            OperationalEvent.user_id.is_(None),
                            OperationalEvent.user_id == user.id,
                        )
                    )
                    .order_by(desc(OperationalEvent.created_at))
                    .limit(25)
                )
                rows = list((await db.scalars(stmt)).all())
            index = next((i for i, row in enumerate(rows) if row.id == last_id), len(rows))
            fresh = rows if last_id is None else rows[:index]
            for row in reversed(fresh):
                data = json.dumps(event_response(row).model_dump(mode="json"))
                yield f"id: {row.id}\nevent: operational_event\ndata: {data}\n\n"
            if rows:
                last_id = rows[0].id
            yield ": keepalive\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/shipments")
async def create_shipment(
    payload: ShipmentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if payload.route_id:
        route = await db.scalar(
            select(GeneratedRoute).where(
                GeneratedRoute.id == payload.route_id, GeneratedRoute.user_id == user.id
            )
        )
        if route is None:
            raise HTTPException(404, "Owned route not found")
    shipment = Shipment(user_id=user.id, reference=payload.reference, route_id=payload.route_id)
    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)
    return {
        "id": shipment.id,
        "reference": shipment.reference,
        "status": shipment.status,
        "tracking_enabled": shipment.tracking_enabled,
    }


@router.patch("/shipments/{shipment_id}/tracking")
async def set_tracking(
    shipment_id: uuid.UUID,
    enabled: bool,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    shipment = await db.scalar(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.user_id == user.id)
    )
    if shipment is None:
        raise HTTPException(404, "Shipment not found")
    shipment.tracking_enabled = enabled
    await db.commit()
    return {"shipment_id": shipment.id, "tracking_enabled": shipment.tracking_enabled}


@router.post("/shipments/{shipment_id}/positions")
async def add_position(
    shipment_id: uuid.UUID,
    payload: ShipmentPositionCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    shipment = await db.scalar(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.user_id == user.id)
    )
    if shipment is None:
        raise HTTPException(404, "Shipment not found")
    if not shipment.tracking_enabled:
        raise HTTPException(409, "Tracking is not enabled for this shipment")
    observed = (
        payload.observed_at
        if payload.observed_at.tzinfo
        else payload.observed_at.replace(tzinfo=timezone.utc)
    )
    now = datetime.now(timezone.utc)
    if observed > now + timedelta(minutes=5):
        raise HTTPException(422, "Position timestamp is in the future")
    age = max(0, int((now - observed.astimezone(timezone.utc)).total_seconds()))
    freshness = "FRESH" if age <= 120 else "AGING" if age <= 900 else "STALE"
    is_simulated = payload.source_type == "SIMULATED"
    provenance = ProvenanceRecord(
        user_id=user.id,
        route_id=shipment.route_id,
        entity_type="shipment_position",
        entity_key=f"{shipment.id}:{observed.isoformat()}",
        decision_input_role="LIVE_SHIPMENT_POSITION",
        canonical_source_type="SIMULATED" if is_simulated else "OPERATOR_INPUT",
        raw_source_state=(
            "SIMULATED"
            if is_simulated
            else f"OPERATOR_DECLARED_UNVERIFIED:{payload.source_type}"
        ),
        observed_at=observed,
        fetched_at=now,
        freshness_state=freshness,
        freshness_seconds=age,
        cache_hit=False,
        used_in_decision=False,
        availability_state="AVAILABLE",
        completeness=1.0,
        value_summary={"latitude": payload.latitude, "longitude": payload.longitude},
        metadata_json={
            "provider": payload.provider,
            "consent": "shipment tracking explicitly enabled",
            "verification_state": (
                "SIMULATED" if is_simulated else "OPERATOR_DECLARED_UNVERIFIED"
            ),
            "provider_claim_verified": False,
        },
    )
    db.add(provenance)
    await db.flush()
    position = ShipmentPosition(
        shipment_id=shipment.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
        heading=payload.heading,
        accuracy_meters=payload.accuracy_meters,
        source_type=payload.source_type,
        provider=payload.provider,
        observed_at=observed,
        received_at=now,
        freshness=freshness,
        provenance_record_id=provenance.id,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return {
        "id": position.id,
        "shipment_id": shipment.id,
        "freshness": freshness,
        "observed_at": observed,
        "received_at": now,
        "source_type": payload.source_type,
    }


@router.get("/shipments")
async def list_shipments(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> dict:
    shipments = (
        await db.scalars(
            select(Shipment)
            .where(Shipment.user_id == user.id)
            .order_by(desc(Shipment.created_at))
        )
    ).all()
    shipment_ids = [shipment.id for shipment in shipments]
    latest_by_shipment: dict[uuid.UUID, ShipmentPosition] = {}
    if shipment_ids:
        ranked_positions = (
            select(
                ShipmentPosition.id.label("position_id"),
                func.row_number()
                .over(
                    partition_by=ShipmentPosition.shipment_id,
                    order_by=(
                        ShipmentPosition.observed_at.desc(),
                        ShipmentPosition.received_at.desc(),
                    ),
                )
                .label("position_rank"),
            )
            .where(ShipmentPosition.shipment_id.in_(shipment_ids))
            .subquery()
        )
        latest_positions = (
            await db.scalars(
                select(ShipmentPosition)
                .join(
                    ranked_positions,
                    ranked_positions.c.position_id == ShipmentPosition.id,
                )
                .where(ranked_positions.c.position_rank == 1)
            )
        ).all()
        latest_by_shipment = {
            position.shipment_id: position for position in latest_positions
        }
    items = []
    for shipment in shipments:
        position = latest_by_shipment.get(shipment.id)
        latest = None
        if position is not None:
            latest = {
                "latitude": position.latitude,
                "longitude": position.longitude,
                "speed": position.speed,
                "observed_at": position.observed_at,
                "freshness": position.freshness,
                "source_type": position.source_type,
            }
        items.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "route_id": shipment.route_id,
                "status": shipment.status,
                "tracking_enabled": shipment.tracking_enabled,
                "latest_position": latest,
            }
        )
    return {"items": items}


@router.post(
    "/train-sync/schedules/{schedule_id}", response_model=TrainSyncResponse
)
async def synchronize_train_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TrainSyncResponse:
    schedule = await db.scalar(
        select(TrainSchedule).where(
            TrainSchedule.id == schedule_id, TrainSchedule.user_id == user.id
        )
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Train schedule not found")
    state = await synchronize_schedule(db, schedule, user.id)
    return train_sync_response(state)


@router.get(
    "/train-sync/schedules/{schedule_id}", response_model=TrainSyncResponse
)
async def train_schedule_sync_state(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TrainSyncResponse:
    state = await db.scalar(
        select(TrainSyncState).where(
            TrainSyncState.schedule_id == schedule_id,
            TrainSyncState.user_id == user.id,
        )
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Train sync state not found")
    return train_sync_response(state)
