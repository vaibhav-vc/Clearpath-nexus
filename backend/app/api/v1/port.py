from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.route import PortBerth
from app.schemas.port import PortBerthResponse, PortSyncStatus
from app.services.port_sync import (
    compute_port_sync,
    fetch_demo_port_schedule,
    fetch_port_schedule,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/berths", response_model=list[PortBerthResponse])
async def list_berths(db: AsyncSession = Depends(get_db)) -> list[PortBerthResponse]:
    result = await db.execute(select(PortBerth))
    return list(result.scalars().all())


@router.get("/sync-status", response_model=PortSyncStatus)
async def port_sync_status(
    db: AsyncSession = Depends(get_db),
    port_id: str = "JNPT_MUMBAI",
    vessel_id: str = "MAERSK_X26",
    train_arrival_hours: float = 24.0,
) -> PortSyncStatus:
    schedule = await fetch_port_schedule(port_id, vessel_id)
    if not schedule.available and settings.DEMO_DATA_ENABLED:
        schedule = await fetch_demo_port_schedule(db, port_id, vessel_id) or schedule

    result = compute_port_sync(train_arrival_hours, schedule)
    if not result.available or result.window is None:
        raise HTTPException(status_code=503, detail=result.warning or "Port schedule unavailable")

    return PortSyncStatus(
        aligned=result.aligned,
        berth_id=result.berth_id or "OPERATOR_INPUT",
        vessel_status=result.vessel_status or "AVAILABLE",
        loading_window_start=result.window.start,
        loading_window_end=result.window.end,
        sync_score=round(result.score, 1),
        warning=result.warning,
    )
