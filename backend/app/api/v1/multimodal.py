from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.multimodal import MultimodalLeg, MultimodalPlan
from app.schemas.multimodal import MultimodalPlanCreate, MultimodalPlanResponse
from app.services.multimodal import evaluate_plan, get_plan, plan_response

router = APIRouter()


@router.post(
    "/plans",
    response_model=MultimodalPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_multimodal_plan(
    payload: MultimodalPlanCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MultimodalPlanResponse:
    """Evaluate operator/provider-supplied legs without inventing missing values."""
    try:
        return await evaluate_plan(db, payload, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/plans", response_model=list[MultimodalPlanResponse])
async def list_multimodal_plans(
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[MultimodalPlanResponse]:
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
    if not plans:
        return []
    legs = list(
        (
            await db.scalars(
                select(MultimodalLeg)
                .where(MultimodalLeg.plan_id.in_([plan.id for plan in plans]))
                .order_by(MultimodalLeg.plan_id, MultimodalLeg.sequence)
            )
        ).all()
    )
    legs_by_plan = {plan.id: [] for plan in plans}
    for leg in legs:
        legs_by_plan[leg.plan_id].append(leg)
    return [plan_response(plan, legs_by_plan[plan.id]) for plan in plans]


@router.get("/plans/{plan_id}", response_model=MultimodalPlanResponse)
async def read_multimodal_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> MultimodalPlanResponse:
    result = await get_plan(db, plan_id, user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Multimodal plan not found")
    return result
