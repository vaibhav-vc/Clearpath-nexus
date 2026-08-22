from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.route import TrainSchedule
from app.services.ixigo_sync import synchronize_schedule

logger = logging.getLogger(__name__)
ACTIVE_SCHEDULE_STATES = {"PLANNED", "READY", "DISPATCHED", "IN_TRANSIT"}


async def _sync_one(schedule_id) -> bool:
    async with AsyncSessionLocal() as db:
        schedule = await db.scalar(
            select(TrainSchedule).where(TrainSchedule.id == schedule_id)
        )
        if schedule is None:
            return False
        await synchronize_schedule(db, schedule, schedule.user_id)
        return True


async def sync_once() -> dict[str, int]:
    if not settings.IXIGO_SYNC_ENABLED:
        return {"synchronized": 0, "skipped_disabled": 1, "failures": 0}
    semaphore = asyncio.Semaphore(4)

    async def bounded(schedule_id) -> bool:
        async with semaphore:
            try:
                return await _sync_one(schedule_id)
            except Exception:
                logger.exception("train_sync_schedule_failed")
                return False

    page_size = 250
    offset = 0
    synchronized = 0
    failures = 0
    while True:
        async with AsyncSessionLocal() as db:
            schedule_ids = list(
                (
                    await db.scalars(
                        select(TrainSchedule.id)
                        .where(
                            TrainSchedule.schedule_status.in_(ACTIVE_SCHEDULE_STATES)
                        )
                        .order_by(
                            TrainSchedule.scheduled_departure, TrainSchedule.id
                        )
                        .offset(offset)
                        .limit(page_size)
                    )
                ).all()
            )
        if not schedule_ids:
            break
        results = await asyncio.gather(*(bounded(item) for item in schedule_ids))
        synchronized += sum(results)
        failures += len(results) - sum(results)
        offset += len(schedule_ids)
        if len(schedule_ids) < page_size:
            break
    return {
        "synchronized": synchronized,
        "skipped_disabled": 0,
        "failures": failures,
    }


async def run() -> None:
    if not settings.IXIGO_SYNC_ENABLED:
        logger.warning(
            "ixigo train synchronization disabled; authorized partner access is required"
        )
        return
    try:
        while True:
            logger.info("train_synchronizer_cycle", extra=await sync_once())
            await asyncio.sleep(max(300, settings.IXIGO_SYNC_INTERVAL_SECONDS))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
