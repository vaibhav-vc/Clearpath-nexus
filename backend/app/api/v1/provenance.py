from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.observability import provider_status
from app.core.security import CurrentUser, get_current_user
from app.models.provenance import DataSource, LineageEdge, ProvenanceRecord, RouteDecisionSnapshot
from app.models.route import GeneratedRoute
from app.schemas.provenance import (
    EvidenceComponent,
    LineageEdgeResponse,
    ProvenanceRecordResponse,
    ProvenanceSummary,
    RecordNeighborhoodResponse,
    RouteEvidenceResponse,
    SourceBrief,
    SourceListResponse,
)

router = APIRouter()


def component_record_ids(
    records: list[ProvenanceRecordResponse],
    edges: list[LineageEdgeResponse],
    direct_items: list[ProvenanceRecordResponse],
) -> list[UUID]:
    """Return direct decision records plus every stored upstream ancestor."""
    available_ids = {record.id for record in records}
    parents_by_child: dict[UUID, set[UUID]] = defaultdict(set)
    for edge in edges:
        parents_by_child[edge.child_record_id].add(edge.parent_record_id)
    included = {item.id for item in direct_items}
    pending = list(included)
    while pending:
        child_id = pending.pop()
        for parent_id in parents_by_child.get(child_id, set()):
            if parent_id in available_ids and parent_id not in included:
                included.add(parent_id)
                pending.append(parent_id)
    return [record.id for record in records if record.id in included]


def _source_brief(source: DataSource, current: dict[str, Any] | None = None) -> SourceBrief:
    return SourceBrief(
        id=source.id,
        key=source.key,
        label=source.display_name,
        category=source.category,
        authority_level=source.authority_level,
        official=source.official,
        free_for_mvp=source.free_for_mvp,
        requires_key=source.requires_key,
        reference_url=source.reference_url,
        license_name=source.license_name,
        attribution_text=source.attribution_text,
        limitations=source.limitations,
        freshness_policy={
            "fresh_seconds": source.default_fresh_seconds,
            "aging_after_seconds": source.aging_after_seconds,
            "stale_after_seconds": source.stale_after_seconds,
        },
        current_status=current,
    )


def _record_response(
    record: ProvenanceRecord, source: DataSource | None
) -> ProvenanceRecordResponse:
    return ProvenanceRecordResponse(
        id=record.id,
        entity_type=record.entity_type,
        entity_key=record.entity_key,
        decision_input_role=record.decision_input_role,
        canonical_source_type=record.canonical_source_type,
        raw_source_state=record.raw_source_state,
        source=_source_brief(source) if source else None,
        observed_at=record.observed_at,
        fetched_at=record.fetched_at,
        valid_until=record.valid_until,
        freshness={"state": record.freshness_state, "age_seconds": record.freshness_seconds},
        cache_hit=record.cache_hit,
        used_in_decision=record.used_in_decision,
        excluded_reason=record.excluded_reason,
        quality={
            "availability": record.availability_state,
            "confidence": float(record.confidence) if record.confidence is not None else None,
            "completeness": float(record.completeness) if record.completeness is not None else None,
        },
        transform={
            "name": record.transform_name,
            "version": record.transform_version,
            "formula_reference": record.formula_reference,
        },
        decision_impact={
            "role": record.decision_input_role,
            "used": record.used_in_decision,
            "use_class": record.metadata_json.get("decision_use"),
            "excluded_reason": record.excluded_reason,
        },
        request_id=record.request_id,
        checksum=record.checksum,
        value_summary=record.value_summary,
        metadata=record.metadata_json,
    )


async def _owned_snapshot(
    db: AsyncSession, route_id: UUID, user_id: str
) -> tuple[GeneratedRoute, RouteDecisionSnapshot]:
    result = await db.execute(
        select(GeneratedRoute, RouteDecisionSnapshot)
        .join(RouteDecisionSnapshot, RouteDecisionSnapshot.route_id == GeneratedRoute.id)
        .where(GeneratedRoute.id == route_id, GeneratedRoute.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Route evidence not found")
    return row[0], row[1]


@router.get("/routes/{route_id}", response_model=RouteEvidenceResponse)
async def get_route_evidence(
    route_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RouteEvidenceResponse:
    """Return the stored decision evidence. This endpoint never refetches providers."""
    route, snapshot = await _owned_snapshot(db, route_id, user.id)
    record_result = await db.execute(
        select(ProvenanceRecord, DataSource)
        .outerjoin(DataSource, DataSource.id == ProvenanceRecord.source_id)
        .where(
            ProvenanceRecord.decision_snapshot_id == snapshot.id,
            ProvenanceRecord.user_id == user.id,
        )
        .order_by(ProvenanceRecord.created_at, ProvenanceRecord.entity_type)
    )
    rows = list(record_result.all())
    records = [_record_response(record, source) for record, source in rows]
    record_ids = [record.id for record, _ in rows]
    edge_result = await db.execute(
        select(LineageEdge).where(
            LineageEdge.parent_record_id.in_(record_ids),
            LineageEdge.child_record_id.in_(record_ids),
        )
    )
    edges = [
        LineageEdgeResponse.model_validate(edge, from_attributes=True)
        for edge in edge_result.scalars()
    ]

    grouped: dict[str, list[ProvenanceRecordResponse]] = defaultdict(list)
    for record in records:
        if record.decision_input_role:
            grouped[record.decision_input_role].append(record)
    components = [
        EvidenceComponent(
            role=role,
            label=role.replace("_", " ").title(),
            status=("EXCLUDED" if all(not item.used_in_decision for item in items) else "TRACED"),
            record_ids=component_record_ids(records, edges, items),
            explanation=(
                next((item.excluded_reason for item in items if item.excluded_reason), None)
                or f"{len(component_record_ids(records, edges, items))} stored evidence record(s) explain this decision input."
            ),
        )
        for role, items in sorted(grouped.items())
    ]
    summary = ProvenanceSummary.model_validate(snapshot.traceability_summary)
    return RouteEvidenceResponse(
        route={
            "id": str(route.id),
            "source_code": route.source_station_code,
            "destination_code": route.dest_station_code,
            "status": route.status,
            "dispatch_status": route.dispatch_status,
        },
        snapshot={
            "id": str(snapshot.id),
            "created_at": snapshot.created_at,
            "reliability_score": snapshot.reliability_score,
            "clearance_state": snapshot.clearance_state,
            "score_breakdown": snapshot.score_breakdown,
            "applied_weights": snapshot.applied_weights,
            "excluded_factors": snapshot.excluded_factors,
            "algorithm_versions": {
                "decision": snapshot.decision_engine_version,
                "routing": snapshot.routing_algorithm_version,
                "scoring": snapshot.scoring_version,
                "clearance": snapshot.clearance_engine_version,
            },
        },
        traceability=summary,
        components=components,
        records=records,
        edges=edges,
        warnings=summary.warnings,
    )


@router.get("/records/{record_id}", response_model=RecordNeighborhoodResponse)
async def get_record_neighborhood(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RecordNeighborhoodResponse:
    owned_result = await db.execute(
        select(ProvenanceRecord, DataSource)
        .outerjoin(DataSource, DataSource.id == ProvenanceRecord.source_id)
        .where(ProvenanceRecord.id == record_id, ProvenanceRecord.user_id == user.id)
    )
    owned = owned_result.one_or_none()
    if owned is None:
        raise HTTPException(status_code=404, detail="Provenance record not found")
    edge_result = await db.execute(
        select(LineageEdge).where(
            or_(LineageEdge.parent_record_id == record_id, LineageEdge.child_record_id == record_id)
        )
    )
    edge_models = list(edge_result.scalars())
    related_ids = {
        edge.parent_record_id if edge.child_record_id == record_id else edge.child_record_id
        for edge in edge_models
    }
    related_rows = []
    if related_ids:
        related_result = await db.execute(
            select(ProvenanceRecord, DataSource)
            .outerjoin(DataSource, DataSource.id == ProvenanceRecord.source_id)
            .where(ProvenanceRecord.id.in_(related_ids), ProvenanceRecord.user_id == user.id)
        )
        related_rows = list(related_result.all())
    response_by_id = {
        record.id: _record_response(record, source) for record, source in related_rows
    }
    edge_models = [
        edge
        for edge in edge_models
        if (
            edge.parent_record_id == record_id and edge.child_record_id in response_by_id
        )
        or (edge.child_record_id == record_id and edge.parent_record_id in response_by_id)
    ]
    parent_ids = {
        edge.parent_record_id for edge in edge_models if edge.child_record_id == record_id
    }
    child_ids = {edge.child_record_id for edge in edge_models if edge.parent_record_id == record_id}
    return RecordNeighborhoodResponse(
        record=_record_response(owned[0], owned[1]),
        parents=[response_by_id[item] for item in parent_ids if item in response_by_id],
        children=[response_by_id[item] for item in child_ids if item in response_by_id],
        edges=[
            LineageEdgeResponse.model_validate(edge, from_attributes=True) for edge in edge_models
        ],
    )


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> SourceListResponse:
    result = await db.execute(
        select(DataSource).where(DataSource.enabled.is_(True)).order_by(DataSource.display_name)
    )
    live_status = provider_status.snapshot()
    items = [
        _source_brief(source, live_status.get(source.key)) for source in result.scalars().all()
    ]
    return SourceListResponse(items=items, total=len(items))


@router.get("/health")
async def source_health(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "providers": provider_status.snapshot(),
        "meaning": "Process-local provider observations; not an SLA.",
    }
