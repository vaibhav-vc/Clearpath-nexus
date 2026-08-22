"""Static/live congestion blending, including every degradation path."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.services.congestion import (
    CongestionSource,
    blend,
    port_congestion_penalty,
    resolve_congestion,
)
from app.services.live_port import PortActivity, PortActivitySource
from app.services.live_rail import CorridorCongestion, RailDataSource, StationCongestion


@dataclass
class FakeSegment:
    congestion_factor: float = 1.0
    historical_delay_hours: float = 0.0


def _corridor(score, source=RailDataSource.LIVE, max_delay=0, observed_at=None):
    return CorridorCongestion(
        source=source,
        stations=[
            StationCongestion(
                "BSL", RailDataSource.LIVE, train_count=3, max_delay_minutes=max_delay
            )
        ],
        score=score,
        fetched_at=datetime.now(timezone.utc),
        observed_at=observed_at or datetime.now(timezone.utc),
    )


_UNAVAILABLE = CorridorCongestion(source=RailDataSource.UNAVAILABLE, detail="feed down")


def patch_feeds(monkeypatch, corridor=None, port=None, rail_raises=False):
    from app.services import congestion as mod

    async def fake_fetch():
        if rail_raises:
            raise RuntimeError("boom")
        return corridor if corridor is not None else _UNAVAILABLE

    monkeypatch.setattr(mod.rail_client, "fetch_corridor", fake_fetch, raising=False)
    monkeypatch.setattr(
        mod.ais_collector,
        "snapshot",
        lambda: port or PortActivity(PortActivitySource.UNAVAILABLE),
        raising=False,
    )
    monkeypatch.setattr(mod.settings, "LIVE_CONGESTION_ENABLED", True, raising=False)
    monkeypatch.setattr(mod.settings, "LIVE_CONGESTION_WEIGHT", 0.6, raising=False)


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ blending


@pytest.mark.parametrize(
    "static,live,weight,expected",
    [(80, 40, 0.0, 80.0), (80, 40, 1.0, 40.0), (80, 40, 0.5, 60.0), (80, 40, 0.6, 56.0)],
)
def test_blend_weights(static, live, weight, expected):
    assert blend(static, live, weight) == expected


def test_blend_clamps_out_of_range_weight():
    assert blend(80, 40, 5.0) == 40.0
    assert blend(80, 40, -3.0) == 80.0


@pytest.mark.parametrize("pct,expected", [(0, 0.0), (40, 10.0), (100, 25.0), (400, 25.0)])
def test_port_penalty_is_capped(pct, expected):
    assert port_congestion_penalty(pct) == expected


# ------------------------------------------------------------- resolution


def test_falls_back_to_static_when_rail_unavailable(monkeypatch):
    patch_feeds(monkeypatch)
    result = run(resolve_congestion([FakeSegment()], dest_code="JNPT"))
    assert result.source is CongestionSource.STATIC_ONLY
    assert result.score == result.static_score
    assert result.uses_live_data is False


def test_rail_exception_never_breaks_scoring(monkeypatch):
    """A telemetry outage must degrade the reading, not fail the request."""
    patch_feeds(monkeypatch, rail_raises=True)
    result = run(resolve_congestion([FakeSegment()], dest_code="JNPT"))
    assert result.source is CongestionSource.STATIC_ONLY
    assert result.score == result.static_score


def test_disabled_flag_skips_live_entirely(monkeypatch):
    patch_feeds(monkeypatch, corridor=_corridor(10.0))
    result = run(resolve_congestion([FakeSegment()], dest_code="JNPT", use_live=False))
    assert result.source is CongestionSource.STATIC_ONLY


def test_live_rail_moves_the_score(monkeypatch):
    patch_feeds(monkeypatch, corridor=_corridor(40.0))
    result = run(resolve_congestion([FakeSegment()], dest_code="NGP"))
    assert result.source is CongestionSource.STATIC_PLUS_LIVE_RAIL
    # static 100 (congestion_factor 1.0), live 40, weight 0.6 -> 64
    assert result.score == 64.0
    assert result.live_rail_score == 40.0


def test_port_congestion_only_applies_to_port_bound_routes(monkeypatch):
    port = PortActivity(
        PortActivitySource.LIVE_AIS, at_anchor=8, congestion_pct=80.0, vessels_tracked=8
    )
    patch_feeds(monkeypatch, corridor=_corridor(40.0), port=port)

    to_port = run(resolve_congestion([FakeSegment()], dest_code="JNPT"))
    inland = run(resolve_congestion([FakeSegment()], dest_code="PUNE"))

    assert to_port.source is CongestionSource.STATIC_PLUS_LIVE_RAIL_AND_PORT
    assert inland.source is CongestionSource.STATIC_PLUS_LIVE_RAIL
    assert to_port.score < inland.score, "port queue must only penalise port-bound cargo"
    assert to_port.port_penalty == 20.0
    assert inland.port_penalty == 0.0


def test_port_bound_route_alerts_on_berth_queue(monkeypatch):
    port = PortActivity(
        PortActivitySource.LIVE_AIS, at_anchor=9, congestion_pct=70.0, vessels_tracked=9
    )
    patch_feeds(monkeypatch, corridor=_corridor(60.0), port=port)
    result = run(resolve_congestion([FakeSegment()], dest_code="JNPT"))
    assert any("at anchor" in a for a in result.alerts)


def test_severe_delay_raises_alert(monkeypatch):
    patch_feeds(monkeypatch, corridor=_corridor(40.0, max_delay=95))
    result = run(resolve_congestion([FakeSegment()], dest_code="NGP"))
    assert any("95 min" in a for a in result.alerts)


def test_score_never_leaves_valid_range(monkeypatch):
    port = PortActivity(PortActivitySource.LIVE_AIS, at_anchor=40, congestion_pct=100.0)
    patch_feeds(monkeypatch, corridor=_corridor(0.0), port=port)
    result = run(resolve_congestion([FakeSegment(congestion_factor=3.0)], dest_code="JNPT"))
    assert 0.0 <= result.score <= 100.0


def test_empty_segment_list_is_safe(monkeypatch):
    patch_feeds(monkeypatch, corridor=_corridor(50.0))
    result = run(resolve_congestion([], dest_code="JNPT"))
    assert 0.0 <= result.score <= 100.0


def test_dest_code_is_case_insensitive(monkeypatch):
    port = PortActivity(PortActivitySource.LIVE_AIS, at_anchor=5, congestion_pct=50.0)
    patch_feeds(monkeypatch, corridor=_corridor(60.0), port=port)
    assert (
        run(resolve_congestion([FakeSegment()], dest_code="jnpt")).source
        is CongestionSource.STATIC_PLUS_LIVE_RAIL_AND_PORT
    )


def test_missing_dest_code_skips_port(monkeypatch):
    port = PortActivity(PortActivitySource.LIVE_AIS, at_anchor=8, congestion_pct=80.0)
    patch_feeds(monkeypatch, corridor=_corridor(60.0), port=port)
    assert (
        run(resolve_congestion([FakeSegment()], dest_code=None)).source
        is CongestionSource.STATIC_PLUS_LIVE_RAIL
    )


def test_cached_rail_and_stale_ais_keep_actual_source_timestamps(monkeypatch):
    rail_observed = datetime.now(timezone.utc) - timedelta(hours=2)
    ais_observed = datetime.now(timezone.utc) - timedelta(minutes=20)
    port = PortActivity(
        PortActivitySource.STALE_AIS,
        at_anchor=8,
        congestion_pct=80.0,
        observed_at=ais_observed,
    )
    patch_feeds(
        monkeypatch,
        corridor=_corridor(40.0, source=RailDataSource.CACHED, observed_at=rail_observed),
        port=port,
    )
    result = run(resolve_congestion([FakeSegment()], dest_code="JNPT"))
    assert result.detail["rail_source"] == "CACHED"
    assert result.detail["rail_observed_at"] == rail_observed.isoformat()
    assert result.detail["port_source"] == "STALE_AIS"
    assert result.detail["port_observed_at"] == ais_observed.isoformat()
