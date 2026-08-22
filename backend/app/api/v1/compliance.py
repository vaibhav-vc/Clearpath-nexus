from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.compliance import (
    ComplianceCheck,
    ComplianceCheckItem,
    ComplianceOverrideEvent,
    ComplianceRuleSource,
    ShipmentDocument,
)
from app.models.route import GeneratedRoute
from app.schemas.compliance import (
    COMPLIANCE_DISCLAIMER,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceItemResponse,
    ComplianceOverrideEventResponse,
    ComplianceOverrideRequest,
    ShipmentDocumentResponse,
)
from app.services.compliance import RULE_PACK_VERSION, RULE_SOURCE_ID, evaluate_compliance_rules

router = APIRouter()


async def _owned_route(db: AsyncSession, route_id: UUID, user_id: str) -> GeneratedRoute:
    result = await db.execute(
        select(GeneratedRoute).where(
            GeneratedRoute.id == route_id, GeneratedRoute.user_id == user_id
        )
    )
    route = result.scalar_one_or_none()
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


async def _owned_check(db: AsyncSession, check_id: UUID, user_id: str) -> ComplianceCheck:
    result = await db.execute(
        select(ComplianceCheck).where(
            ComplianceCheck.id == check_id, ComplianceCheck.user_id == user_id
        )
    )
    check = result.scalar_one_or_none()
    if check is None:
        raise HTTPException(status_code=404, detail="Compliance check not found")
    return check


def _item_response(
    item: ComplianceCheckItem, source: ComplianceRuleSource
) -> ComplianceItemResponse:
    return ComplianceItemResponse(
        id=item.id,
        rule_key=item.rule_key,
        rule_version=item.rule_version,
        status=item.status,
        explanation=item.explanation,
        recommended_action=item.recommended_action,
        penalty_exposure=item.penalty_exposure,
        evidence=item.evidence,
        rule_source={
            "title": source.title,
            "authority": source.authority,
            "jurisdiction": source.jurisdiction,
            "reference_url": source.reference_url,
            "version": source.version,
            "official": source.official,
            "retrieved_at": source.retrieved_at,
            "checksum": source.checksum,
            "limitations": source.limitations,
        },
    )


async def _responses(
    db: AsyncSession, checks: list[ComplianceCheck]
) -> list[ComplianceCheckResponse]:
    if not checks:
        return []
    check_ids = [check.id for check in checks]
    item_result = await db.execute(
        select(ComplianceCheckItem, ComplianceRuleSource)
        .join(ComplianceRuleSource, ComplianceRuleSource.id == ComplianceCheckItem.rule_source_id)
        .where(ComplianceCheckItem.check_id.in_(check_ids))
        .order_by(ComplianceCheckItem.created_at, ComplianceCheckItem.rule_key)
    )
    items_by_check: dict[UUID, list[ComplianceItemResponse]] = defaultdict(list)
    for item, source in item_result.all():
        items_by_check[item.check_id].append(_item_response(item, source))

    event_result = await db.execute(
        select(ComplianceOverrideEvent)
        .where(
            ComplianceOverrideEvent.check_id.in_(check_ids),
            ComplianceOverrideEvent.user_id.in_([check.user_id for check in checks]),
        )
        .order_by(ComplianceOverrideEvent.created_at, ComplianceOverrideEvent.id)
    )
    events_by_check: dict[UUID, list[ComplianceOverrideEventResponse]] = defaultdict(list)
    for event in event_result.scalars():
        events_by_check[event.check_id].append(
            ComplianceOverrideEventResponse.model_validate(event, from_attributes=True)
        )

    document_result = await db.execute(
        select(ShipmentDocument).where(
            ShipmentDocument.check_id.in_(check_ids),
            ShipmentDocument.user_id.in_([check.user_id for check in checks]),
        )
    )
    documents_by_check: dict[UUID, list[ShipmentDocumentResponse]] = defaultdict(list)
    for document in document_result.scalars():
        if document.check_id is not None:
            documents_by_check[document.check_id].append(
                ShipmentDocumentResponse.model_validate(document, from_attributes=True)
            )

    return [
        ComplianceCheckResponse(
            id=check.id,
            route_id=check.route_id,
            overall_status=check.overall_status,
            rule_pack_version=check.rule_pack_version,
            disclaimer=check.disclaimer,
            overridden=check.overridden,
            override_reason=check.override_reason,
            overridden_by=check.overridden_by,
            overridden_at=check.overridden_at,
            created_at=check.created_at,
            items=items_by_check[check.id],
            documents=documents_by_check[check.id],
            overrides=events_by_check[check.id],
        )
        for check in checks
    ]


async def _response(db: AsyncSession, check: ComplianceCheck) -> ComplianceCheckResponse:
    return (await _responses(db, [check]))[0]


@router.post("/routes/{route_id}/checks", response_model=ComplianceCheckResponse, status_code=201)
async def create_check(
    route_id: UUID,
    payload: ComplianceCheckRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ComplianceCheckResponse:
    route = await _owned_route(db, route_id, user.id)
    overall, results, eta = evaluate_compliance_rules(
        route_status=route.status,
        estimated_hours=float(route.estimated_hours) if route.estimated_hours is not None else None,
        payload=payload,
    )
    check = ComplianceCheck(
        user_id=user.id,
        route_id=route.id,
        overall_status=overall,
        rule_pack_version=RULE_PACK_VERSION,
        disclaimer=COMPLIANCE_DISCLAIMER,
        input_summary={
            "document_count": len(payload.documents),
            "document_types": sorted(
                {item.document_type.upper() for item in payload.documents}
            ),
            "cargo_declaration_complete": payload.cargo_declaration_complete,
            "human_approval_obtained": payload.human_approval_obtained,
            "estimated_completion_at": eta.isoformat() if eta else None,
            "references_present": {
                "transporter": bool(payload.transporter_reference),
                "shipment": bool(payload.shipment_reference),
                "eway_bill": bool(payload.eway_bill_reference),
                "port_customs": bool(payload.port_customs_reference),
            },
        },
    )
    db.add(check)
    await db.flush()
    documents = [
        ShipmentDocument(
            user_id=user.id,
            route_id=route.id,
            check_id=check.id,
            **document.model_dump(),
        )
        for document in payload.documents
    ]
    db.add_all(documents)
    db.add_all(
        [
            ComplianceCheckItem(
                check_id=check.id,
                rule_source_id=RULE_SOURCE_ID,
                rule_key=result.rule_key,
                rule_version=RULE_PACK_VERSION,
                status=result.status,
                explanation=result.explanation,
                recommended_action=result.recommended_action,
                penalty_exposure=result.penalty_exposure,
                evidence=result.evidence,
            )
            for result in results
        ]
    )
    await db.commit()
    await db.refresh(check)
    return await _response(db, check)


@router.get("/routes/{route_id}/checks", response_model=list[ComplianceCheckResponse])
async def list_checks(
    route_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[ComplianceCheckResponse]:
    await _owned_route(db, route_id, user.id)
    result = await db.execute(
        select(ComplianceCheck)
        .where(ComplianceCheck.route_id == route_id, ComplianceCheck.user_id == user.id)
        .order_by(ComplianceCheck.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return await _responses(db, list(result.scalars().all()))


@router.get("/checks/{check_id}", response_model=ComplianceCheckResponse)
async def get_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ComplianceCheckResponse:
    return await _response(db, await _owned_check(db, check_id, user.id))


@router.post("/checks/{check_id}/override", response_model=ComplianceCheckResponse)
async def override_check(
    check_id: UUID,
    payload: ComplianceOverrideRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ComplianceCheckResponse:
    check = await _owned_check(db, check_id, user.id)
    check.overridden = True
    check.override_reason = payload.reason
    check.overridden_by = user.id
    check.overridden_at = datetime.now(timezone.utc)
    db.add(
        ComplianceOverrideEvent(
            check_id=check.id,
            user_id=user.id,
            reason=payload.reason,
            created_at=check.overridden_at,
        )
    )
    await db.commit()
    await db.refresh(check)
    return await _response(db, check)
