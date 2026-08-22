from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.route import GeneratedRoute
from app.models.live_ops import ProviderObservation, ShipmentPosition

logger = logging.getLogger(__name__)


async def purge_expired_routes(db: AsyncSession, retention_days: int | None = None) -> int:
    """Purge GeneratedRoute records older than retention_days to prevent unbounded DB growth."""
    days = retention_days if retention_days is not None else settings.ROUTE_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = delete(GeneratedRoute).where(GeneratedRoute.created_at < cutoff)
    result = await db.execute(stmt)
    await db.commit()

    deleted_count = int(result.rowcount or 0)
    logger.info(
        "purged_expired_routes",
        extra={"deleted_count": deleted_count, "cutoff": cutoff.isoformat()},
    )
    return deleted_count


async def purge_live_observations(db: AsyncSession) -> dict[str, int]:
    """Apply separately configurable retention to high-volume operational data."""
    now = datetime.now(timezone.utc)
    observation_result = await db.execute(
        delete(ProviderObservation).where(
            ProviderObservation.created_at
            < now - timedelta(days=settings.LIVE_OBSERVATION_RETENTION_DAYS)
        )
    )
    position_result = await db.execute(
        delete(ShipmentPosition).where(
            ShipmentPosition.created_at < now - timedelta(days=settings.POSITION_RETENTION_DAYS)
        )
    )
    await db.commit()
    return {
        "provider_observations": int(observation_result.rowcount or 0),
        "shipment_positions": int(position_result.rowcount or 0),
    }
