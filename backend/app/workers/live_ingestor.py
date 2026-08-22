from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.live_ops import ProviderRuntimeState
from app.services.data_retention import purge_live_observations
from app.services.event_engine import events_from_observation
from app.services.live_data import PROVIDERS, cache_latest, persist_envelope, utc_now

logger = logging.getLogger(__name__)
RETENTION_INTERVAL = timedelta(hours=24)
_last_retention_at: datetime | None = None

MONITORED_WEATHER_POINTS = (
    ("NGP", 21.1458, 79.0882),
    ("BSL", 21.0469, 75.7886),
    ("KYN", 19.2350, 73.1299),
    ("JNPT", 18.9497, 72.9510),
)


async def _record_runtime(db, envelope) -> None:
    state = await db.scalar(
        select(ProviderRuntimeState).where(
            ProviderRuntimeState.provider_key == envelope.provider_key
        )
    )
    if state is None:
        state = ProviderRuntimeState(provider_key=envelope.provider_key)
        db.add(state)
    provider = PROVIDERS[envelope.provider_key]
    state.current_state = provider.breaker.state
    state.consecutive_failures = provider.breaker.failures
    state.freshness = envelope.freshness
    state.rate_limited = envelope.status == "RATE_LIMITED"
    state.authentication_state = (
        "AUTH_REQUIRED" if envelope.status == "AUTH_REQUIRED" else "NOT_REQUIRED"
    )
    state.next_attempt_at = (
        provider.breaker.opened_at
        + timedelta(seconds=provider.breaker.cooldown_seconds)
        if provider.breaker.state == "OPEN" and provider.breaker.opened_at
        else None
    )
    if envelope.status in {"LIVE", "CACHED", "AGING"}:
        state.last_success_at = utc_now()
    else:
        state.last_failure_at = utc_now()
    state.latency_ms = envelope.data.get("provider_latency_ms")


async def _purge_retention_if_due(
    db, now: datetime | None = None
) -> dict[str, int]:
    global _last_retention_at
    checked_at = now or datetime.now(timezone.utc)
    if (
        _last_retention_at is not None
        and checked_at - _last_retention_at < RETENTION_INTERVAL
    ):
        return {}
    try:
        deleted = await purge_live_observations(db)
    except Exception:
        logger.exception("live_retention_cycle_failed")
        try:
            await db.rollback()
        except Exception:
            logger.exception("live_retention_rollback_failed")
        return {"retention_failures": 1}
    _last_retention_at = checked_at
    return {
        "expired_observations": deleted["provider_observations"],
        "expired_positions": deleted["shipment_positions"],
    }


async def ingest_once() -> dict[str, int]:
    counters = {"observations": 0, "events": 0, "failures": 0}
    jobs: list[tuple[str, str, str | None, dict]] = []
    if settings.ENABLE_LIVE_WEATHER:
        jobs.extend(
            (
                "open_meteo",
                "WEATHER",
                code,
                {"location": {"latitude": lat, "longitude": lon}},
            )
            for code, lat, lon in MONITORED_WEATHER_POINTS
        )
    jobs.append(("noaa_swpc", "SPACE_WEATHER", None, {}))
    results = await asyncio.gather(
        *(PROVIDERS[key].fetch(context) for key, _, _, context in jobs)
    )
    async with AsyncSessionLocal() as db:
        for (_, observation_type, entity_id, _), envelope in zip(jobs, results):
            await _record_runtime(db, envelope)
            observation = await persist_envelope(
                db,
                envelope,
                observation_type,
                "CORRIDOR_POINT" if entity_id else None,
                entity_id,
            )
            cache_type = observation_type if entity_id is None else f"{observation_type}:{entity_id}"
            await cache_latest(envelope, cache_type)
            if observation is not None:
                counters["observations"] += 1
                if settings.ENABLE_EVENT_ENGINE:
                    generated = events_from_observation(observation, envelope)
                    db.add_all(generated)
                    counters["events"] += len(generated)
            if envelope.status in {"UNAVAILABLE", "INVALID", "RATE_LIMITED"}:
                counters["failures"] += 1
        await db.commit()
        counters.update(await _purge_retention_if_due(db))
    return counters


async def run() -> None:
    if not settings.LIVE_DATA_ENABLED:
        logger.warning("Live ingestor disabled by LIVE_DATA_ENABLED=false")
        return
    logger.info("live_ingestor_started")
    try:
        while True:
            try:
                counters = await ingest_once()
                logger.info("live_ingestor_cycle", extra=counters)
            except Exception:
                logger.exception("live_ingestor_cycle_failed")
            await asyncio.sleep(max(60, settings.LIVE_INGEST_INTERVAL_SECONDS))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
