from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.compliance import ComplianceCheck, ComplianceOverrideEvent
from app.models.live_ops import (
    OperationalEvent,
    ProviderRuntimeState,
    Shipment,
    ShipmentPosition,
    TrainSyncState,
)
from app.models.ml import MLPrediction
from app.models.multimodal import MultimodalPlan
from app.models.provenance import LineageEdge, ProvenanceRecord, RouteDecisionSnapshot
from app.models.route import GeneratedRoute, TrainSchedule
from app.schemas.operations import (
    AuditExport,
    OperationsOverview,
    OperationsTwin,
    ShipmentTwin,
)

router = APIRouter()


async def _group_counts(db: AsyncSession, column, *criteria) -> dict[str, int]:
    rows = (
        await db.execute(
            select(column, func.count()).where(*criteria).group_by(column)
        )
    ).all()
    return {str(key): int(count) for key, count in rows}


@router.get("/overview", response_model=OperationsOverview)
async def operations_overview(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OperationsOverview:
    routes_total = int(
        await db.scalar(
            select(func.count()).select_from(GeneratedRoute).where(
                GeneratedRoute.user_id == user.id
            )
        )
        or 0
    )
    shipments = await _group_counts(db, Shipment.status, Shipment.user_id == user.id)
    schedules = await _group_counts(
        db, TrainSchedule.schedule_status, TrainSchedule.user_id == user.id
    )
    events = await _group_counts(
        db,
        OperationalEvent.severity,
        OperationalEvent.state == "OPEN",
        or_(OperationalEvent.user_id == user.id, OperationalEvent.user_id.is_(None)),
    )
    compliance = await _group_counts(
        db, ComplianceCheck.overall_status, ComplianceCheck.user_id == user.id
    )
    multimodal = await _group_counts(
        db, MultimodalPlan.status, MultimodalPlan.user_id == user.id
    )
    train_sync = await _group_counts(
        db, TrainSyncState.status, TrainSyncState.user_id == user.id
    )
    prediction_count = int(
        await db.scalar(
            select(func.count()).select_from(MLPrediction).where(
                MLPrediction.user_id == user.id
            )
        )
        or 0
    )
    provenance_total = int(
        await db.scalar(
            select(func.count()).select_from(ProvenanceRecord).where(
                ProvenanceRecord.user_id == user.id,
                ProvenanceRecord.decision_input_role.is_not(None),
            )
        )
        or 0
    )
    has_lineage = exists(
        select(LineageEdge.id).where(
            or_(
                LineageEdge.parent_record_id == ProvenanceRecord.id,
                LineageEdge.child_record_id == ProvenanceRecord.id,
            )
        )
    )
    provenance_traced = int(
        await db.scalar(
            select(func.count()).select_from(ProvenanceRecord).where(
                ProvenanceRecord.user_id == user.id,
                ProvenanceRecord.decision_input_role.is_not(None),
                or_(
                    ProvenanceRecord.source_id.is_not(None),
                    ProvenanceRecord.canonical_source_type == "OPERATOR_INPUT",
                    has_lineage,
                ),
            )
        )
        or 0
    )
    providers = list((await db.scalars(select(ProviderRuntimeState))).all())
    return OperationsOverview(
        generated_at=datetime.now(timezone.utc),
        product_version="6.0.0",
        routes_total=routes_total,
        shipments_by_status=shipments,
        schedules_by_status=schedules,
        open_events_by_severity=events,
        compliance_by_status=compliance,
        multimodal_by_status=multimodal,
        train_sync_by_status=train_sync,
        prediction_count=prediction_count,
        traceability={
            "traced_records": provenance_traced,
            "total_records": provenance_total,
            "percent": (
                round(provenance_traced / provenance_total * 100, 1)
                if provenance_total
                else 0.0
            ),
            "basis": (
                "owned decision inputs with an identified source, explicit operator "
                "origin, or stored lineage edge"
            ),
        },
        provider_health=[
            {
                "provider": item.provider_key,
                "circuit": item.current_state,
                "freshness": item.freshness,
                "last_success_at": (
                    item.last_success_at.isoformat() if item.last_success_at else None
                ),
                "rate_limited": item.rate_limited,
                "authentication_state": item.authentication_state,
            }
            for item in providers
        ],
        notices=[
            "Decision support only; qualified humans retain operational authority.",
            "The shipment twin is a state projection, not railway signalling or train control.",
            "Unavailable costs, risk, and provider data remain explicitly unavailable.",
        ],
    )


@router.get("/twin", response_model=OperationsTwin)
async def operations_twin(
    limit: int = Query(default=100, ge=1, le=250),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OperationsTwin:
    latest_position_id = (
        select(ShipmentPosition.id)
        .where(ShipmentPosition.shipment_id == Shipment.id)
        .order_by(ShipmentPosition.observed_at.desc())
        .limit(1)
        .correlate(Shipment)
        .scalar_subquery()
    )
    open_event_count = (
        select(func.count())
        .select_from(OperationalEvent)
        .where(
            OperationalEvent.shipment_id == Shipment.id,
            OperationalEvent.user_id == user.id,
            OperationalEvent.state == "OPEN",
        )
        .correlate(Shipment)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(Shipment, ShipmentPosition, open_event_count.label("open_events"))
            .outerjoin(ShipmentPosition, ShipmentPosition.id == latest_position_id)
            .where(Shipment.user_id == user.id)
            .order_by(Shipment.updated_at.desc())
            .limit(limit)
        )
    ).all()
    results: list[ShipmentTwin] = []
    for shipment, position, event_count in rows:
        results.append(
            ShipmentTwin(
                shipment_id=shipment.id,
                reference=shipment.reference,
                status=shipment.status,
                tracking_enabled=shipment.tracking_enabled,
                route_id=shipment.route_id,
                latest_position=(
                    {
                        "latitude": position.latitude,
                        "longitude": position.longitude,
                        "speed": position.speed,
                        "heading": position.heading,
                        "observed_at": position.observed_at.isoformat(),
                        "freshness": position.freshness,
                        "source_type": position.source_type,
                    }
                    if position
                    else None
                ),
                open_event_count=event_count,
                state_source=(
                    (
                        "SIMULATED"
                        if position.source_type == "SIMULATED"
                        else f"OPERATOR_DECLARED_UNVERIFIED:{position.source_type}"
                    )
                    if position
                    else "UNAVAILABLE"
                ),
            )
        )
    return OperationsTwin(
        generated_at=datetime.now(timezone.utc),
        model_type="OPERATIONAL_STATE_PROJECTION",
        shipments=results,
        disclaimer=(
            "This projection summarizes authenticated operational records; it is not "
            "signalling, interlocking, ATP, certified dispatch control, or a physics twin."
        ),
    )


@router.get("/audit/export", response_model=AuditExport)
async def audit_export(
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AuditExport:
    records: list[dict] = []
    snapshots = list(
        (
            await db.scalars(
                select(RouteDecisionSnapshot)
                .where(RouteDecisionSnapshot.user_id == user.id)
                .order_by(RouteDecisionSnapshot.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    records.extend(
        {
            "type": "ROUTE_DECISION",
            "id": str(item.id),
            "created_at": item.created_at.isoformat(),
            "status": item.clearance_state,
            "engine_version": item.decision_engine_version,
        }
        for item in snapshots
    )
    overrides = list(
        (
            await db.scalars(
                select(ComplianceOverrideEvent)
                .where(ComplianceOverrideEvent.user_id == user.id)
                .order_by(ComplianceOverrideEvent.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    records.extend(
        {
            "type": "COMPLIANCE_OVERRIDE",
            "id": str(item.id),
            "created_at": item.created_at.isoformat(),
            "check_id": str(item.check_id),
            "reason": item.reason,
        }
        for item in overrides
    )
    predictions = list(
        (
            await db.scalars(
                select(MLPrediction)
                .where(MLPrediction.user_id == user.id)
                .order_by(MLPrediction.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    records.extend(
        {
            "type": "DELAY_PREDICTION",
            "id": str(item.id),
            "created_at": item.created_at.isoformat(),
            "model": f"{item.model_name}:{item.model_version}",
            "model_status": item.model_status,
            "fallback_reason": item.fallback_reason,
        }
        for item in predictions
    )
    plans = list(
        (
            await db.scalars(
                select(MultimodalPlan)
                .where(MultimodalPlan.user_id == user.id)
                .order_by(MultimodalPlan.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    records.extend(
        {
            "type": "MULTIMODAL_DECISION",
            "id": str(item.id),
            "created_at": item.created_at.isoformat(),
            "status": item.status,
            "recommendation": item.recommendation,
        }
        for item in plans
    )
    records.sort(key=lambda item: item["created_at"], reverse=True)
    return AuditExport(
        generated_at=datetime.now(timezone.utc),
        format_version="clearpath-audit-v1",
        owner_scope="CURRENT_AUTHENTICATED_USER",
        records=records[:limit],
        limitations=[
            "This export is an application audit extract, not a government filing.",
            "Global provider observations are intentionally excluded from the owned export.",
        ],
    )
