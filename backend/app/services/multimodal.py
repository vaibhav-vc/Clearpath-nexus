from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.multimodal import MultimodalLeg, MultimodalPlan
from app.models.compliance import ComplianceCheck
from app.models.provenance import LineageEdge, ProvenanceRecord
from app.schemas.multimodal import (
    MultimodalLegInput,
    MultimodalLegResponse,
    MultimodalPlanCreate,
    MultimodalPlanResponse,
)

COST_SOURCE_MAP = {
    "VERIFIED_TARIFF": "IMPORTED_DOCUMENT",
    "OPERATOR_INPUT": "OPERATOR_INPUT",
    "UNAVAILABLE": "UNAVAILABLE",
}


def _decision(legs: list[MultimodalLegInput]) -> tuple[str, str, str]:
    hard_blocked = any(
        leg.compliance_status == "BLOCKED"
        or any(item.status == "HARD_BLOCKED" for item in leg.constraints)
        for leg in legs
    )
    manual_review = any(
        leg.compliance_status in {"MANUAL_REVIEW", "NOT_ASSESSED"}
        or any(item.status == "UNKNOWN" for item in leg.constraints)
        for leg in legs
    )
    warning = any(
        leg.compliance_status == "WARNING"
        or any(item.status == "WARNING" for item in leg.constraints)
        for leg in legs
    )
    known_risks = [leg.risk_score for leg in legs if leg.risk_score is not None]
    missing_risk = any(leg.risk_score is None for leg in legs)
    elevated_risk = bool(known_risks and max(known_risks) >= 70)
    if hard_blocked:
        return "HARD_BLOCKED", "HOLD", "BLOCKED"
    if manual_review or missing_risk:
        return "REVIEW_REQUIRED", "MANUAL_REVIEW", "MANUAL_REVIEW"
    if warning or elevated_risk:
        return "EVALUATED", "PROCEED_WITH_REVIEW", "WARNING"
    return "EVALUATED", "PROCEED", "PASSED"


def _record(
    *,
    user_id: str,
    plan_id: str,
    sequence: int | None,
    role: str,
    canonical_source_type: str,
    raw_state: str,
    availability: str,
    used: bool,
    value: dict,
    provider: str | None = None,
    dataset: str | None = None,
    reference: str | None = None,
    observed_at: datetime | None = None,
    freshness: str = "NOT_APPLICABLE",
) -> ProvenanceRecord:
    suffix = "decision" if sequence is None else f"leg:{sequence}:{role.lower()}"
    return ProvenanceRecord(
        user_id=user_id,
        entity_type="multimodal_plan" if sequence is None else "multimodal_leg",
        entity_key=f"{plan_id}:{suffix}",
        decision_input_role=role,
        canonical_source_type=canonical_source_type,
        raw_source_state=raw_state,
        observed_at=observed_at,
        fetched_at=datetime.now(timezone.utc),
        freshness_state=freshness,
        cache_hit=canonical_source_type == "CACHED_PROVIDER",
        used_in_decision=used,
        excluded_reason=None if used else "Input was unavailable and excluded",
        availability_state=availability,
        completeness=1.0 if used else 0.0,
        transform_name="multimodal_evaluator" if sequence is None else None,
        transform_version="1.0.0" if sequence is None else None,
        value_summary=value,
        metadata_json={
            "provider": provider,
            "dataset": dataset,
            "source_reference": reference,
        },
    )


def _computed_freshness(
    source_type: str, observed_at: datetime | None
) -> str:
    if source_type == "UNAVAILABLE":
        return "UNAVAILABLE"
    if source_type in {
        "OPERATOR_INPUT",
        "SEEDED_BASELINE",
        "DERIVED",
        "SIMULATED",
        "IMPORTED_DOCUMENT",
    }:
        return "NOT_APPLICABLE"
    if observed_at is None:
        return "UNAVAILABLE"
    observed = (
        observed_at.replace(tzinfo=timezone.utc)
        if observed_at.tzinfo is None
        else observed_at.astimezone(timezone.utc)
    )
    age = datetime.now(timezone.utc) - observed
    if age <= timedelta(minutes=15):
        return "FRESH"
    if age <= timedelta(hours=1):
        return "AGING"
    return "STALE"


async def evaluate_plan(
    db: AsyncSession, payload: MultimodalPlanCreate, user_id: str
) -> MultimodalPlanResponse:
    submitted_legs = payload.legs
    check_ids = {
        leg.compliance_check_id
        for leg in submitted_legs
        if leg.compliance_check_id is not None
    }
    checks = list(
        (
            await db.scalars(
                select(ComplianceCheck).where(
                    ComplianceCheck.id.in_(check_ids),
                    ComplianceCheck.user_id == user_id,
                )
            )
        ).all()
    ) if check_ids else []
    checks_by_id = {check.id: check for check in checks}
    if len(checks_by_id) != len(check_ids):
        raise ValueError("one or more ComplianceGuard checks are unavailable to this owner")
    compliance_map = {
        "PASS": "PASSED",
        "PASSED": "PASSED",
        "WARNING": "WARNING",
        "BLOCKED": "BLOCKED",
        "MANUAL_REVIEW": "MANUAL_REVIEW",
    }
    legs = [
        leg.model_copy(
            update={
                "compliance_status": compliance_map.get(
                    checks_by_id[leg.compliance_check_id].overall_status,
                    "MANUAL_REVIEW",
                )
            }
        )
        if leg.compliance_check_id is not None
        else leg
        for leg in submitted_legs
    ]
    status, recommendation, compliance = _decision(legs)
    known_costs = [leg.cost_amount for leg in legs if leg.cost_amount is not None]
    known_risks = [leg.risk_score for leg in legs if leg.risk_score is not None]
    compliance_evidence = sum(leg.compliance_check_id is not None for leg in legs)
    traced = len(legs) + len(known_costs) + len(known_risks) + compliance_evidence
    expected = len(legs) * 4
    traceability = {
        "traced_inputs": traced,
        "expected_inputs": expected,
        "traceability_percent": round(traced / expected * 100, 1),
        "unavailable_cost_inputs": len(legs) - len(known_costs),
        "unavailable_risk_inputs": len(legs) - len(known_risks),
        "unavailable_compliance_inputs": len(legs) - compliance_evidence,
        "method": "counted leg, cost, risk, and owned ComplianceGuard inputs",
    }
    plan = MultimodalPlan(
        user_id=user_id,
        name=payload.name,
        origin=payload.origin,
        destination=payload.destination,
        status=status,
        recommendation=recommendation,
        total_distance_km=round(sum(leg.distance_km for leg in legs), 3),
        total_eta_minutes=sum(leg.estimated_minutes for leg in legs),
        total_cost=round(sum(known_costs), 2) if len(known_costs) == len(legs) else None,
        cost_currency=payload.cost_currency,
        cost_completeness=round(len(known_costs) / len(legs), 4),
        overall_risk_score=max(known_risks) if known_risks else None,
        compliance_status=compliance,
        inputs_snapshot={
            "submitted": payload.model_dump(mode="json"),
            "resolved_legs": [leg.model_dump(mode="json") for leg in legs],
        },
        traceability_summary=traceability,
    )
    db.add(plan)
    await db.flush()

    parent_records: list[ProvenanceRecord] = []
    leg_rows: list[MultimodalLeg] = []
    for sequence, leg in enumerate(legs, start=1):
        base_record = _record(
            user_id=user_id,
            plan_id=str(plan.id),
            sequence=sequence,
            role="LEG_OPERATOR_INPUT",
            canonical_source_type="OPERATOR_INPUT",
            raw_state="OPERATOR_INPUT",
            availability="AVAILABLE",
            used=True,
            value={
                "mode": leg.mode,
                "origin": leg.origin,
                "destination": leg.destination,
                "distance_km": leg.distance_km,
                "estimated_minutes": leg.estimated_minutes,
                "constraints": [item.model_dump() for item in leg.constraints],
            },
        )
        cost_available = leg.cost_amount is not None
        cost_source = COST_SOURCE_MAP[leg.cost_source_type]
        cost_freshness = _computed_freshness(
            cost_source, leg.source_observed_at
        )
        cost_record = _record(
            user_id=user_id,
            plan_id=str(plan.id),
            sequence=sequence,
            role="LEG_COST",
            canonical_source_type=cost_source,
            raw_state=leg.cost_source_type,
            availability="AVAILABLE" if cost_available else "UNAVAILABLE",
            used=cost_available,
            value={"amount": leg.cost_amount, "currency": payload.cost_currency},
            provider=leg.source_provider,
            dataset=leg.source_dataset,
            reference=leg.source_reference,
            observed_at=leg.source_observed_at,
            freshness=cost_freshness,
        )
        risk_available = leg.risk_score is not None
        risk_freshness = _computed_freshness(
            leg.risk_source_type, leg.source_observed_at
        )
        risk_record = _record(
            user_id=user_id,
            plan_id=str(plan.id),
            sequence=sequence,
            role="LEG_RISK",
            canonical_source_type=leg.risk_source_type,
            raw_state=leg.risk_source_type,
            availability="AVAILABLE" if risk_available else "UNAVAILABLE",
            used=risk_available,
            value={"risk_score": leg.risk_score},
            provider=leg.source_provider,
            dataset=leg.source_dataset,
            reference=leg.source_reference,
            observed_at=leg.source_observed_at,
            freshness=risk_freshness,
        )
        compliance_available = leg.compliance_check_id is not None
        compliance_record = _record(
            user_id=user_id,
            plan_id=str(plan.id),
            sequence=sequence,
            role="LEG_COMPLIANCE",
            canonical_source_type="DERIVED" if compliance_available else "UNAVAILABLE",
            raw_state=(
                "COMPLIANCEGUARD_CHECK" if compliance_available else "NOT_ASSESSED"
            ),
            availability="AVAILABLE" if compliance_available else "UNAVAILABLE",
            used=compliance_available,
            value={
                "compliance_check_id": (
                    str(leg.compliance_check_id)
                    if leg.compliance_check_id is not None
                    else None
                ),
                "resolved_status": leg.compliance_status,
            },
        )
        db.add_all([base_record, cost_record, risk_record, compliance_record])
        await db.flush()
        parent_records.extend(
            [base_record, cost_record, risk_record, compliance_record]
        )
        row = MultimodalLeg(
            plan_id=plan.id,
            sequence=sequence,
            mode=leg.mode,
            origin=leg.origin,
            destination=leg.destination,
            distance_km=leg.distance_km,
            estimated_minutes=leg.estimated_minutes,
            cost_amount=leg.cost_amount,
            cost_source_type=leg.cost_source_type,
            risk_score=leg.risk_score,
            risk_source_type=leg.risk_source_type,
            compliance_status=leg.compliance_status,
            compliance_check_id=leg.compliance_check_id,
            source_provider=leg.source_provider,
            source_dataset=leg.source_dataset,
            source_observed_at=leg.source_observed_at,
            freshness_state=(
                risk_freshness if risk_available else cost_freshness
            ),
            constraints=[item.model_dump() for item in leg.constraints],
            provenance_record_id=base_record.id,
        )
        db.add(row)
        leg_rows.append(row)

    decision_record = _record(
        user_id=user_id,
        plan_id=str(plan.id),
        sequence=None,
        role="MULTIMODAL_DECISION",
        canonical_source_type="DERIVED",
        raw_state="DERIVED",
        availability="AVAILABLE",
        used=True,
        value={
            "status": status,
            "recommendation": recommendation,
            "compliance_status": compliance,
            "traceability": traceability,
        },
    )
    db.add(decision_record)
    await db.flush()
    db.add_all(
        LineageEdge(
            parent_record_id=record.id,
            child_record_id=decision_record.id,
            relationship="APPLIED_TO",
        )
        for record in parent_records
    )
    await db.commit()
    await db.refresh(plan)
    for row in leg_rows:
        await db.refresh(row)
    return plan_response(plan, leg_rows)


def plan_response(
    plan: MultimodalPlan, legs: list[MultimodalLeg]
) -> MultimodalPlanResponse:
    return MultimodalPlanResponse(
        id=plan.id,
        name=plan.name,
        origin=plan.origin,
        destination=plan.destination,
        status=plan.status,
        recommendation=plan.recommendation,
        total_distance_km=plan.total_distance_km,
        total_eta_minutes=plan.total_eta_minutes,
        total_cost=float(plan.total_cost) if plan.total_cost is not None else None,
        cost_currency=plan.cost_currency,
        cost_completeness=plan.cost_completeness,
        overall_risk_score=plan.overall_risk_score,
        compliance_status=plan.compliance_status,
        traceability_summary=plan.traceability_summary,
        created_at=plan.created_at,
        legs=[
            MultimodalLegResponse(
                id=leg.id,
                sequence=leg.sequence,
                mode=leg.mode,
                origin=leg.origin,
                destination=leg.destination,
                distance_km=leg.distance_km,
                estimated_minutes=leg.estimated_minutes,
                cost_amount=(
                    float(leg.cost_amount) if leg.cost_amount is not None else None
                ),
                cost_source_type=leg.cost_source_type,
                risk_score=leg.risk_score,
                risk_source_type=leg.risk_source_type,
                compliance_status=leg.compliance_status,
                compliance_check_id=leg.compliance_check_id,
                freshness_state=leg.freshness_state,
                constraints=leg.constraints,
                provenance_record_id=leg.provenance_record_id,
            )
            for leg in sorted(legs, key=lambda item: item.sequence)
        ],
    )


async def get_plan(
    db: AsyncSession, plan_id, user_id: str
) -> MultimodalPlanResponse | None:
    plan = await db.scalar(
        select(MultimodalPlan).where(
            MultimodalPlan.id == plan_id, MultimodalPlan.user_id == user_id
        )
    )
    if plan is None:
        return None
    legs = list(
        (
            await db.scalars(
                select(MultimodalLeg)
                .where(MultimodalLeg.plan_id == plan.id)
                .order_by(MultimodalLeg.sequence)
            )
        ).all()
    )
    return plan_response(plan, legs)
