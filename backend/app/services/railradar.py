from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.observability import provider_status
from app.services.space_weather import space_weather_service

logger = logging.getLogger(__name__)

# RailRadar tracks passenger/PRS trains via the public NTES network, not
# freight consists. This is a demo/proof-of-concept live-data layer, not a
# substitute for a real freight-operations feed (RAILWAY_OPERATIONS_FEED).
UNAVAILABLE_TRAFFIC = {
    "available": False,
    "provider": "railradar",
    "state": "NOT_CONFIGURED",
    "trains": [],
    "message": "Live train-traffic provider is not configured.",
}


def _unavailable(state: str, message: str) -> dict[str, Any]:
    """An off envelope that says which kind of off it is.

    A rejected key and an absent key are different problems with different
    fixes, and reporting the first as the second sends an operator looking for
    a configuration fault that does not exist.
    """
    return {
        "available": False,
        "provider": "railradar",
        "state": state,
        "trains": [],
        "message": message,
    }

# How many trains (max) to pull live status for per corridor query, to stay
# well inside the free sandbox's 1,000 requests/month.
_MAX_LIVE_LOOKUPS = 5


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.RAILRADAR_API_KEY}"}


def _corridor_candidates(data: Any) -> list[dict[str, Any]]:
    """Pull the train list out of a /trains/between payload.

    The endpoint wraps its results in an object -- {from, to, trains, count} --
    so treating `data` as the list itself raised `unhashable type: 'slice'`
    against a real key. A bare list is still accepted in case the shape
    changes back.
    """
    if isinstance(data, dict):
        trains = data.get("trains")
        return [item for item in trains if isinstance(item, dict)] if isinstance(trains, list) else []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


async def fetch_trains_between(source_code: str, dest_code: str) -> dict[str, Any]:
    """Return live running status for trains between two station codes.

    Always returns a dict with an `available` flag — never raises — so
    callers can treat this the same way as every other honest-degradation
    provider in this codebase: show real data when it's there, say plainly
    when it isn't, never fabricate a result.
    """
    if not settings.RAILRADAR_API_KEY:
        return UNAVAILABLE_TRAFFIC

    cache_key = f"railradar:between:{source_code}:{dest_code}"
    cached = await space_weather_service._cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=6.0, headers=_headers()) as client:
            between_resp = await client.get(
                f"{settings.RAILRADAR_BASE_URL}/trains/between/{source_code}/{dest_code}"
            )
            between_resp.raise_for_status()
            envelope = between_resp.json()
            if not envelope.get("success"):
                raise ValueError("RailRadar returned an unsuccessful response envelope")

            candidates = _corridor_candidates(envelope.get("data"))
            trains: list[dict[str, Any]] = []
            alerts: list[str] = []

            for candidate in candidates[:_MAX_LIVE_LOOKUPS]:
                # /trains/between nests identity under `train`, unlike
                # /trains/{n}/live which carries trainNumber at the top level.
                identity = candidate.get("train") or {}
                train_number = identity.get("number") or candidate.get("trainNumber")
                if not train_number:
                    continue
                live_entry = {
                    "train_number": str(train_number),
                    "train_name": identity.get("name")
                    or candidate.get("trainName")
                    or "Unknown",
                    "status": "unknown",
                    "delay_minutes": None,
                }
                try:
                    live_resp = await client.get(
                        f"{settings.RAILRADAR_BASE_URL}/trains/{train_number}/live"
                    )
                    live_resp.raise_for_status()
                    live_envelope = live_resp.json()
                    if live_envelope.get("success"):
                        live_data = live_envelope.get("data", {})
                        delay = live_data.get("delayMinutes")
                        live_entry["status"] = live_data.get("status", "unknown")
                        live_entry["delay_minutes"] = delay
                        if isinstance(delay, (int, float)) and delay >= 30:
                            alerts.append(
                                f"{train_number} ({live_entry['train_name']}) running {int(delay)}m late"
                            )
                except Exception as live_exc:
                    logger.warning(
                        "RailRadar live lookup failed for train %s: %s", train_number, live_exc
                    )
                trains.append(live_entry)

            payload = {
                "available": True,
                "provider": "railradar",
                "source_code": source_code,
                "dest_code": dest_code,
                "trains": trains,
                "alerts": alerts,
            }
            await space_weather_service._cache_set(cache_key, payload, ttl=120)
            provider_status.record_success("railradar")
            return payload
    except httpx.HTTPStatusError as exc:
        provider_status.record_failure("railradar")
        status_code = exc.response.status_code
        logger.warning(
            "RailRadar corridor fetch rejected for %s->%s: HTTP %s",
            source_code,
            dest_code,
            status_code,
        )
        if status_code in (401, 403):
            return _unavailable(
                "AUTH_REQUIRED",
                "RailRadar rejected the configured API key. The key is present but not accepted.",
            )
        if status_code == 429:
            return _unavailable(
                "RATE_LIMITED",
                "The RailRadar request quota is exhausted, so no live traffic was retrieved.",
            )
        return _unavailable(
            "UNAVAILABLE",
            f"RailRadar returned HTTP {status_code}, so no live traffic was retrieved.",
        )
    except Exception as exc:
        provider_status.record_failure("railradar")
        logger.warning(
            "RailRadar corridor fetch failed for %s->%s: %s", source_code, dest_code, exc
        )
        return _unavailable(
            "UNAVAILABLE",
            "The live train-traffic provider could not be reached.",
        )
