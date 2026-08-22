"""Port synchronisation.

Design rule: this module never invents a berth schedule.

Port alignment carries 30% of the reliability score. Silently substituting a
mock when the feed is down makes that 30% a constant nobody can see, so every
result carries an explicit `source` and callers are expected to branch on it.

Three sources, in order of preference:
  LIVE_FEED      - a real maritime feed is configured and answered
  OPERATOR_INPUT - the operator typed in the vessel loading window
  UNAVAILABLE    - we have nothing; port alignment is excluded from scoring
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.route import PortBerth

logger = logging.getLogger(__name__)


class PortDataSource(str, Enum):
    LIVE_FEED = "LIVE_FEED"
    OPERATOR_INPUT = "OPERATOR_INPUT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class LoadingWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class PortSchedule:
    source: PortDataSource
    berth_id: str | None = None
    vessel_status: str | None = None
    window: LoadingWindow | None = None
    detail: str | None = None

    @property
    def available(self) -> bool:
        return self.source is not PortDataSource.UNAVAILABLE and self.window is not None


@dataclass(frozen=True)
class PortSyncResult:
    """Outcome of port alignment. `score` is meaningless unless `available`."""

    source: PortDataSource
    available: bool
    score: float
    aligned: bool
    warning: str | None = None
    berth_id: str | None = None
    vessel_status: str | None = None
    window: LoadingWindow | None = None
    evaluated_at: datetime | None = None
    train_arrival_hours: float | None = None


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _window_from_payload(payload: dict[str, Any]) -> LoadingWindow:
    raw = payload["loading_window"]
    return LoadingWindow(start=_parse_iso(raw["start_time"]), end=_parse_iso(raw["end_time"]))


async def fetch_port_schedule(
    port_id: str,
    vessel_id: str,
    operator_window: LoadingWindow | None = None,
) -> PortSchedule:
    """Resolve a berth schedule. Never fabricates one."""

    # An operator-supplied window is authoritative: a human read the manifest.
    if operator_window is not None:
        return PortSchedule(
            source=PortDataSource.OPERATOR_INPUT,
            berth_id=None,
            vessel_status="OPERATOR_DECLARED",
            window=operator_window,
            detail="Loading window entered by operator",
        )

    if not settings.MARITIME_BERTH_DATA_FEED:
        return PortSchedule(
            source=PortDataSource.UNAVAILABLE,
            detail="No maritime berth feed configured (MARITIME_BERTH_DATA_FEED unset)",
        )

    url = f"{settings.MARITIME_BERTH_DATA_FEED.rstrip('/')}/berths/schedule"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"port_id": port_id, "vessel_id": vessel_id})
            resp.raise_for_status()
            payload = resp.json()
        return PortSchedule(
            source=PortDataSource.LIVE_FEED,
            berth_id=payload.get("berth_id"),
            vessel_status=payload.get("vessel_status"),
            window=_window_from_payload(payload),
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Port feed unavailable for %s/%s: %s", port_id, vessel_id, exc)
        return PortSchedule(
            source=PortDataSource.UNAVAILABLE,
            detail=f"Berth feed unreachable: {type(exc).__name__}",
        )


async def fetch_demo_port_schedule(
    db: AsyncSession,
    port_id: str,
    vessel_id: str,
) -> PortSchedule | None:
    """Read explicitly enabled local seed data; never used outside demo mode."""
    berth = await db.scalar(
        select(PortBerth)
        .where(PortBerth.berth_identifier == port_id, PortBerth.vessel_name == vessel_id)
        .limit(1)
    )
    if berth is None:
        berth = await db.scalar(
            select(PortBerth).where(PortBerth.vessel_name == vessel_id).limit(1)
        )
    if berth is None:
        return None
    return PortSchedule(
        source=PortDataSource.OPERATOR_INPUT,
        berth_id=str(berth.id),
        vessel_status="DEMO_SCHEDULED",
        window=LoadingWindow(start=berth.window_start, end=berth.window_end),
        detail="Explicitly enabled local demo seed",
    )


def compute_port_sync(
    train_arrival_hours: float,
    schedule: PortSchedule,
    now: datetime | None = None,
) -> PortSyncResult:
    """Score how well the train lands inside the vessel loading window."""

    now = now or datetime.now(timezone.utc)
    if not schedule.available or schedule.window is None:
        return PortSyncResult(
            source=schedule.source,
            available=False,
            score=0.0,
            aligned=False,
            warning=(
                "Port alignment unavailable - excluded from reliability score. "
                f"({schedule.detail or 'no berth data'})"
            ),
            evaluated_at=now,
            train_arrival_hours=train_arrival_hours,
        )

    window = schedule.window
    arrival = now + timedelta(hours=train_arrival_hours)

    if arrival < window.start:
        gap_hours = (window.start - arrival).total_seconds() / 3600
        score = max(40.0, 100.0 - gap_hours * 3)
        warning = f"Train arrives {gap_hours:.1f}h early - yard dwell risk"
        aligned = False
    elif arrival > window.end:
        score = 0.0
        warning = "CRITICAL: Train misses vessel loading window"
        aligned = False
    else:
        span = max((window.end - window.start).total_seconds(), 1.0)
        window_pct = (arrival - window.start).total_seconds() / span
        score = max(60.0, min(100.0, 100.0 - abs(window_pct - 0.3) * 30))
        warning = None
        aligned = True

    return PortSyncResult(
        source=schedule.source,
        available=True,
        score=score,
        aligned=aligned,
        warning=warning,
        berth_id=schedule.berth_id,
        vessel_status=schedule.vessel_status,
        window=window,
        evaluated_at=now,
        train_arrival_hours=train_arrival_hours,
    )


def compute_port_sync_score(
    train_arrival_hours: float, loading_window: dict[str, str]
) -> tuple[float, str | None]:
    """Backwards-compatible shim for existing callers. Prefer compute_port_sync."""
    schedule = PortSchedule(
        source=PortDataSource.LIVE_FEED,
        window=LoadingWindow(
            start=_parse_iso(loading_window["start_time"]),
            end=_parse_iso(loading_window["end_time"]),
        ),
    )
    result = compute_port_sync(train_arrival_hours, schedule)
    return result.score, result.warning
