"""JNPT port activity from live AIS (aisstream.io, free, BETA).

SCOPE - read this before extending:

    AIS tells us WHERE ships are and whether they are anchored or moored.
    AIS does NOT broadcast berth loading windows.

    So this module produces port CONGESTION, not port SCHEDULE. The
    train-vs-loading-window alignment in port_sync.py still requires operator
    input. Deriving a "loading window" from AIS would be the same fabrication
    bug we removed from port_sync.

Transport notes:
  - aisstream refuses browser/CORS connections by design, so this must live
    server-side. That matches our architecture.
  - The service is explicitly BETA with no SLA. Treat dropouts as normal.
  - It is a push stream, not request/response: we hold one long-lived socket
    and keep a rolling snapshot that the API reads.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"

# JNPT / Nhava Sheva approach and anchorage, Mumbai harbour.
# [[NE corner], [SW corner]] - aisstream accepts either corner order.
JNPT_BBOX: list[list[float]] = [[19.05, 73.05], [18.85, 72.80]]

# Tighter box over the container terminals themselves, used to tell a vessel
# working a berth from one waiting in the roads.
JNPT_BERTH_BBOX: tuple[float, float, float, float] = (18.93, 18.97, 72.92, 72.99)

# AIS navigational status codes (ITU-R M.1371).
NAV_UNDERWAY_ENGINE = 0
NAV_AT_ANCHOR = 1
NAV_MOORED = 5

# A vessel that has not reported in this long is dropped from the snapshot.
VESSEL_STALE_AFTER = timedelta(minutes=45)


class PortActivitySource(str, Enum):
    LIVE_AIS = "LIVE_AIS"
    STALE_AIS = "STALE_AIS"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class VesselState:
    mmsi: int
    name: str | None
    lat: float
    lon: float
    nav_status: int
    sog: float
    seen_at: datetime

    @property
    def at_anchor(self) -> bool:
        return self.nav_status == NAV_AT_ANCHOR

    @property
    def moored(self) -> bool:
        return self.nav_status == NAV_MOORED

    @property
    def in_berth_area(self) -> bool:
        lat_lo, lat_hi, lon_lo, lon_hi = JNPT_BERTH_BBOX
        return lat_lo <= self.lat <= lat_hi and lon_lo <= self.lon <= lon_hi


@dataclass(frozen=True)
class PortActivity:
    """A snapshot of observed vessel activity. Congestion only - not schedule."""

    source: PortActivitySource
    vessels_tracked: int = 0
    at_anchor: int = 0
    moored_at_berth: int = 0
    underway: int = 0
    congestion_pct: float | None = None  # 0 = clear, 100 = gridlocked
    observed_at: datetime | None = None
    detail: str | None = None

    @property
    def available(self) -> bool:
        return self.source is not PortActivitySource.UNAVAILABLE


def parse_ais_message(raw: dict[str, Any]) -> VesselState | None:
    """Extract a vessel state from an aisstream envelope. None if not a position."""
    if raw.get("MessageType") != "PositionReport":
        return None

    report = (raw.get("Message") or {}).get("PositionReport") or {}
    meta = raw.get("MetaData") or {}

    mmsi = report.get("UserID") or meta.get("MMSI")
    lat = report.get("Latitude", meta.get("latitude"))
    lon = report.get("Longitude", meta.get("longitude"))
    if mmsi is None or lat is None or lon is None:
        return None

    # aisstream uses 91/181 as the AIS "position unavailable" sentinels.
    if abs(lat) > 90 or abs(lon) > 180:
        return None

    # AIS pads fixed-width string fields with '@' and spaces; both must go.
    raw_name = meta.get("ShipName")
    name = raw_name.strip().rstrip("@").strip() if isinstance(raw_name, str) else None

    # NavigationalStatus can arrive as null on malformed frames. 15 = "undefined".
    nav_raw = report.get("NavigationalStatus")
    nav_status = int(nav_raw) if isinstance(nav_raw, (int, float)) else 15

    try:
        return VesselState(
            mmsi=int(mmsi),
            name=name or None,
            lat=float(lat),
            lon=float(lon),
            nav_status=nav_status,
            sog=float(report.get("Sog") or 0.0),
            seen_at=datetime.now(timezone.utc),
        )
    except (TypeError, ValueError):
        return None


def anchorage_to_congestion_pct(at_anchor: int, moored: int) -> float:
    """Ships waiting at anchor are the congestion signal.

    JNPT works roughly 8-10 container berths. A handful of vessels in the roads
    is routine; a dozen means the queue is not clearing.

        0-2 anchored  -> 0-20    normal
        3-6           -> 20-55   building
        7-12          -> 55-85   congested
        13+           -> 85-100  gridlocked

    Berth occupancy nudges it up: a full quay plus a queue is worse than a
    queue with berths free.
    """
    if at_anchor <= 2:
        base = at_anchor * 10.0
    elif at_anchor <= 6:
        base = 20.0 + (at_anchor - 2) * 8.75
    elif at_anchor <= 12:
        base = 55.0 + (at_anchor - 6) * 5.0
    else:
        base = min(100.0, 85.0 + (at_anchor - 12) * 3.0)

    berth_pressure = min(10.0, moored * 1.25)
    return round(min(100.0, base + berth_pressure), 1)


class AisCollector:
    """Holds one aisstream socket and exposes a rolling snapshot."""

    def __init__(self) -> None:
        self._vessels: dict[int, VesselState] = {}
        self._task: asyncio.Task | None = None
        self._last_message_at: datetime | None = None
        self._lock = asyncio.Lock()

    # -- snapshot ---------------------------------------------------------

    def _prune(self) -> None:
        cutoff = datetime.now(timezone.utc) - VESSEL_STALE_AFTER
        self._vessels = {m: v for m, v in self._vessels.items() if v.seen_at >= cutoff}

    def snapshot(self) -> PortActivity:
        if not settings.AISSTREAM_API_KEY:
            return PortActivity(PortActivitySource.UNAVAILABLE, detail="AISSTREAM_API_KEY not set")

        self._prune()
        if not self._vessels:
            return PortActivity(
                PortActivitySource.UNAVAILABLE,
                detail="No AIS positions received yet for JNPT",
            )

        vessels = list(self._vessels.values())
        at_anchor = sum(1 for v in vessels if v.at_anchor)
        moored = sum(1 for v in vessels if v.moored and v.in_berth_area)
        underway = sum(1 for v in vessels if v.nav_status == NAV_UNDERWAY_ENGINE)

        stale = self._last_message_at is None or datetime.now(
            timezone.utc
        ) - self._last_message_at > timedelta(minutes=10)

        return PortActivity(
            source=PortActivitySource.STALE_AIS if stale else PortActivitySource.LIVE_AIS,
            vessels_tracked=len(vessels),
            at_anchor=at_anchor,
            moored_at_berth=moored,
            underway=underway,
            congestion_pct=anchorage_to_congestion_pct(at_anchor, moored),
            observed_at=self._last_message_at,
            detail="Stream idle >10min" if stale else None,
        )

    # -- ingestion --------------------------------------------------------

    def ingest(self, raw: dict[str, Any]) -> bool:
        """Apply one message. Returns True if it updated a vessel.

        Never raises: a single malformed frame must not tear down the socket
        and trigger a reconnect/backoff cycle.
        """
        try:
            state = parse_ais_message(raw)
        except Exception:
            logger.debug("Skipping unparseable AIS frame", exc_info=True)
            return False
        if state is None:
            return False
        self._vessels[state.mmsi] = state
        self._last_message_at = state.seen_at
        return True

    async def _run(self) -> None:
        import websockets  # imported lazily so the dep is optional at import time

        subscription = json.dumps(
            {
                "APIKey": settings.AISSTREAM_API_KEY,
                "BoundingBoxes": [JNPT_BBOX],
                "FilterMessageTypes": ["PositionReport"],
            }
        )
        backoff = 2.0
        while True:
            try:
                async with websockets.connect(AIS_STREAM_URL) as ws:
                    # Subscription must arrive within 3s or the socket is closed.
                    await ws.send(subscription)
                    backoff = 2.0
                    logger.info("AIS stream connected for JNPT")
                    async for message in ws:
                        try:
                            payload = json.loads(message)
                        except json.JSONDecodeError:
                            continue
                        if "error" in payload:
                            logger.error("aisstream error: %s", payload["error"])
                            break
                        self.ingest(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("AIS stream dropped (%s); reconnecting in %.0fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120.0)  # BETA service: back off politely

    async def start(self) -> None:
        if not settings.AISSTREAM_API_KEY:
            logger.info("AISSTREAM_API_KEY not set - port activity stays UNAVAILABLE")
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="ais-collector")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


ais_collector = AisCollector()
