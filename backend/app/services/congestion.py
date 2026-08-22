"""Corridor congestion resolution: static baseline blended with live feeds.

Why blend rather than replace:

  The seeded `congestion_factor` on each LineSegment encodes segment-specific
  characteristics - gradient, single vs double track, junction density. Live
  RailRadar data knows none of that; it reports how the NTES passenger network
  is running right now, corridor-wide.

  Each knows something the other does not, so neither should override the
  other. Live data adjusts the baseline; it does not replace the model.

Port congestion is applied only to routes that actually terminate at the port -
ships queueing at JNPT are irrelevant to a Nagpur-Pune move.

Provenance discipline is the same as everywhere else in this codebase: the
result says where every number came from, and missing live data falls back to
the static value rather than to zero.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings
from app.services.live_port import PortActivity, ais_collector
from app.services.live_rail import CorridorCongestion, rail_client

logger = logging.getLogger(__name__)

# Station codes that mean "this route ends at the port".
PORT_TERMINAL_CODES = frozenset({"JNPT"})


class CongestionSource(str, Enum):
    STATIC_ONLY = "STATIC_ONLY"
    STATIC_PLUS_LIVE_RAIL = "STATIC_PLUS_LIVE_RAIL"
    STATIC_PLUS_LIVE_RAIL_AND_PORT = "STATIC_PLUS_LIVE_RAIL_AND_PORT"


@dataclass(frozen=True)
class CongestionAssessment:
    """Final congestion score plus a full account of how it was reached."""

    score: float
    source: CongestionSource
    static_score: float
    live_rail_score: float | None = None
    port_congestion_pct: float | None = None
    port_penalty: float = 0.0
    live_weight: float = 0.0
    alerts: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def uses_live_data(self) -> bool:
        return self.source is not CongestionSource.STATIC_ONLY


def _static_congestion(segments: list[Any]) -> float:
    """Seeded baseline from router_engine.

    Imported lazily and deliberately: router_engine pulls in GeoAlchemy and the
    ORM models, and this module is pure arithmetic over telemetry. Keeping the
    import inside the call lets congestion logic be exercised without the whole
    geospatial stack, and avoids a needless import cycle.
    """
    from app.services.router_engine import compute_congestion_score

    return compute_congestion_score(segments)


def blend(static_score: float, live_score: float, live_weight: float) -> float:
    """Weighted blend, clamped to the valid range."""
    live_weight = max(0.0, min(1.0, live_weight))
    return round(static_score * (1.0 - live_weight) + live_score * live_weight, 1)


def port_congestion_penalty(congestion_pct: float) -> float:
    """Convert port congestion (0-100, high = bad) into a congestion-score penalty.

    Capped at 25 points. A gridlocked port degrades a corridor score but must
    not dominate it - the train still has to physically get there, and that is
    what the rest of the score measures.
    """
    return round(min(25.0, congestion_pct * 0.25), 1)


async def resolve_congestion(
    segments: list[Any],
    dest_code: str | None = None,
    use_live: bool | None = None,
) -> CongestionAssessment:
    """Resolve corridor congestion, preferring live data when it is available."""

    static_score = _static_congestion(segments)

    if use_live is None:
        use_live = settings.LIVE_CONGESTION_ENABLED
    if not use_live:
        return CongestionAssessment(
            score=static_score,
            source=CongestionSource.STATIC_ONLY,
            static_score=static_score,
            detail={"reason": "Live congestion disabled"},
        )

    alerts: list[str] = []

    # --- live rail -------------------------------------------------------
    try:
        corridor: CorridorCongestion = await rail_client.fetch_corridor()
    except Exception as exc:  # a telemetry feed must never break scoring
        logger.warning("Live rail lookup failed: %s", exc)
        corridor = None  # type: ignore[assignment]

    if corridor is None or not corridor.available:
        reason = corridor.detail if corridor is not None else "Live rail lookup errored"
        return CongestionAssessment(
            score=static_score,
            source=CongestionSource.STATIC_ONLY,
            static_score=static_score,
            detail={"reason": reason or "No live rail data"},
        )

    live_weight = settings.LIVE_CONGESTION_WEIGHT
    score = blend(static_score, corridor.score, live_weight)
    source = CongestionSource.STATIC_PLUS_LIVE_RAIL

    worst = max(
        (s for s in corridor.stations if s.available),
        key=lambda s: s.max_delay_minutes,
        default=None,
    )
    if worst is not None and worst.max_delay_minutes >= 60:
        alerts.append(
            f"Live: {worst.station_code} reporting delays up to " f"{worst.max_delay_minutes} min"
        )

    # --- live port (only when the route actually ends at the port) --------
    port_pct: float | None = None
    penalty = 0.0
    bound_for_port = bool(dest_code) and dest_code.upper() in PORT_TERMINAL_CODES

    if bound_for_port:
        try:
            activity: PortActivity = ais_collector.snapshot()
        except Exception as exc:
            logger.warning("AIS snapshot failed: %s", exc)
            activity = None  # type: ignore[assignment]

        if activity is not None and activity.available and activity.congestion_pct is not None:
            port_pct = activity.congestion_pct
            penalty = port_congestion_penalty(port_pct)
            score = round(max(0.0, score - penalty), 1)
            source = CongestionSource.STATIC_PLUS_LIVE_RAIL_AND_PORT
            if activity.at_anchor >= 7:
                alerts.append(
                    f"Live AIS: {activity.at_anchor} vessels at anchor off JNPT "
                    f"- berth queue not clearing"
                )

    return CongestionAssessment(
        score=score,
        source=source,
        static_score=static_score,
        live_rail_score=corridor.score,
        port_congestion_pct=port_pct,
        port_penalty=penalty,
        live_weight=live_weight,
        alerts=alerts,
        detail={
            "rail_source": corridor.source.value,
            "rail_observed_at": corridor.observed_at.isoformat()
            if corridor.observed_at
            else None,
            "rail_fetched_at": corridor.fetched_at.isoformat() if corridor.fetched_at else None,
            "stations_live": sum(1 for s in corridor.stations if s.available),
            "stations_total": len(corridor.stations),
            "port_applied": bound_for_port,
            "port_source": activity.source.value
            if bound_for_port and activity is not None and activity.available
            else None,
            "port_observed_at": activity.observed_at.isoformat()
            if bound_for_port
            and activity is not None
            and activity.available
            and activity.observed_at
            else None,
            "rail_budget_remaining": rail_client.budget.remaining,
        },
    )
