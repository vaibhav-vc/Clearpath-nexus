"""Live-feed parsing and scoring, verified against recorded vendor payloads.

No network here by design: these fixtures are the documented response shapes
from railradar.in/docs and aisstream.io/documentation. They protect the parsing
and scoring logic. Live connectivity is a separate smoke check with real keys.
"""

import json
import pathlib
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.services.live_port import (
    AisCollector,
    PortActivitySource,
    VesselState,
    anchorage_to_congestion_pct,
    parse_ais_message,
)
from app.services.live_rail import (
    RailDataSource,
    RailRadarClient,
    StationCongestion,
    delay_to_congestion_score,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# --------------------------------------------------------------------- rail


def test_railradar_cache_preserves_original_observation_time() -> None:
    observed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    client = RailRadarClient()
    client._cache["BSL"] = (
        time.monotonic(),
        StationCongestion(
            "BSL",
            RailDataSource.LIVE,
            train_count=2,
            observed_at=observed_at,
        ),
    )
    cached = client._cached("BSL")
    assert cached is not None
    assert cached.source is RailDataSource.CACHED
    assert cached.observed_at == observed_at


def test_parses_live_station_board():
    reading = RailRadarClient.parse_station_board("BSL", fixture("railradar_station_live.json"))
    assert reading.source is RailDataSource.LIVE
    assert reading.train_count == 4
    assert reading.at_station_count == 1
    assert reading.max_delay_minutes == 60
    # (0 + 45 + 60 + 15) / 4
    assert reading.mean_delay_minutes == 30.0


def test_error_envelope_becomes_unavailable_not_zero():
    reading = RailRadarClient.parse_station_board("BSL", fixture("railradar_error_429.json"))
    assert reading.source is RailDataSource.UNAVAILABLE
    assert reading.available is False
    assert "quota" in reading.detail.lower()


def test_empty_board_is_live_but_uncongested():
    payload = {"success": True, "data": {"trains": []}}
    reading = RailRadarClient.parse_station_board("MMR", payload)
    assert reading.source is RailDataSource.LIVE
    assert reading.train_count == 0


def test_missing_delay_field_does_not_crash():
    payload = {
        "success": True,
        "data": {"trains": [{"train": {"number": "1"}, "live": {"type": "upcoming"}}]},
    }
    reading = RailRadarClient.parse_station_board("KYN", payload)
    assert reading.train_count == 1
    assert reading.mean_delay_minutes == 0.0


@pytest.mark.parametrize(
    "delay,expected",
    [(0, 100.0), (15, 85.0), (30, 70.0), (60, 40.0), (120, 10.0), (180, 0.0), (400, 0.0)],
)
def test_congestion_breakpoints(delay, expected):
    r = [StationCongestion("BSL", RailDataSource.LIVE, train_count=1, mean_delay_minutes=delay)]
    assert delay_to_congestion_score(r) == expected


def test_congestion_is_monotonic():
    scores = [
        delay_to_congestion_score(
            [StationCongestion("X", RailDataSource.LIVE, train_count=1, mean_delay_minutes=d)]
        )
        for d in range(0, 200, 5)
    ]
    assert all(a >= b for a, b in zip(scores, scores[1:])), "score must not rise with delay"


def test_busier_station_weighs_more():
    """A 60-min delay across 10 trains should outweigh 0 min at 1 train."""
    readings = [
        StationCongestion("BSL", RailDataSource.LIVE, train_count=10, mean_delay_minutes=60),
        StationCongestion("MMR", RailDataSource.LIVE, train_count=1, mean_delay_minutes=0),
    ]
    assert delay_to_congestion_score(readings) < 50


def test_budget_blocks_before_rate_limit():
    client = RailRadarClient()
    client.budget.monthly_limit = 3
    assert [client.budget.spend() for _ in range(4)] == [True, True, True, False]
    assert client.budget.remaining == 0


# --------------------------------------------------------------------- port


def test_parses_ais_position_report():
    state = parse_ais_message(fixture("ais_position_report.json"))
    assert state is not None
    assert state.mmsi == 419000123
    assert state.name == "MAERSK KOLKATA"
    assert state.moored is True
    assert state.in_berth_area is True


def test_non_position_messages_ignored():
    assert parse_ais_message({"MessageType": "ShipStaticData", "Message": {}}) is None


def test_sentinel_coordinates_rejected():
    """AIS uses 91/181 to mean 'position unavailable'."""
    raw = fixture("ais_position_report.json")
    raw["Message"]["PositionReport"]["Latitude"] = 91.0
    raw["Message"]["PositionReport"]["Longitude"] = 181.0
    raw["MetaData"]["latitude"] = 91.0
    raw["MetaData"]["longitude"] = 181.0
    assert parse_ais_message(raw) is None


@pytest.mark.parametrize(
    "anchored,expected_band",
    [(0, (0, 15)), (2, (15, 30)), (5, (40, 60)), (10, (70, 90)), (20, (95, 100))],
)
def test_congestion_bands(anchored, expected_band):
    pct = anchorage_to_congestion_pct(anchored, moored=2)
    lo, hi = expected_band
    assert lo <= pct <= hi, f"{anchored} anchored -> {pct}, expected {expected_band}"


def test_congestion_never_exceeds_100():
    assert anchorage_to_congestion_pct(500, 500) == 100.0


def test_snapshot_unavailable_without_key(monkeypatch):
    from app.services import live_port

    monkeypatch.setattr(live_port.settings, "AISSTREAM_API_KEY", "", raising=False)
    assert AisCollector().snapshot().source is PortActivitySource.UNAVAILABLE


def test_snapshot_counts_vessel_states(monkeypatch):
    from app.services import live_port

    monkeypatch.setattr(live_port.settings, "AISSTREAM_API_KEY", "test-key", raising=False)
    collector = AisCollector()
    now = datetime.now(timezone.utc)

    def vessel(mmsi, nav, lat=18.95, lon=72.95):
        return VesselState(mmsi, f"V{mmsi}", lat, lon, nav, 0.0, now)

    for v in [
        vessel(1, 1, lat=19.02, lon=72.85),  # at anchor, in the roads
        vessel(2, 1, lat=19.01, lon=72.86),  # at anchor
        vessel(3, 5),  # moored at berth
        vessel(4, 0),  # underway
    ]:
        collector._vessels[v.mmsi] = v
    collector._last_message_at = now

    snap = collector.snapshot()
    assert snap.source is PortActivitySource.LIVE_AIS
    assert (snap.at_anchor, snap.moored_at_berth, snap.underway) == (2, 1, 1)
    assert snap.congestion_pct is not None


def test_stale_stream_is_labelled(monkeypatch):
    from app.services import live_port

    monkeypatch.setattr(live_port.settings, "AISSTREAM_API_KEY", "test-key", raising=False)
    collector = AisCollector()
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    collector._vessels[1] = VesselState(1, "V", 18.95, 72.95, 5, 0.0, recent)
    collector._last_message_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    assert collector.snapshot().source is PortActivitySource.STALE_AIS


def test_stale_vessels_are_pruned(monkeypatch):
    from app.services import live_port

    monkeypatch.setattr(live_port.settings, "AISSTREAM_API_KEY", "test-key", raising=False)
    collector = AisCollector()
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    collector._vessels[1] = VesselState(1, "GHOST", 18.95, 72.95, 1, 0.0, old)
    collector._last_message_at = old
    assert collector.snapshot().source is PortActivitySource.UNAVAILABLE


def test_ingest_roundtrip(monkeypatch):
    from app.services import live_port

    monkeypatch.setattr(live_port.settings, "AISSTREAM_API_KEY", "test-key", raising=False)
    collector = AisCollector()
    assert collector.ingest(fixture("ais_position_report.json")) is True
    assert collector.ingest({"MessageType": "Interrogation"}) is False
    assert collector.snapshot().vessels_tracked == 1


# ------------------------------------------------- regressions (found by probing)


def test_malformed_success_envelope_is_not_reported_as_clear_corridor():
    """Regression: {"success": true} with no data block used to parse as LIVE
    with 0 trains, scoring the corridor 100/100 clear. Silent optimism."""
    for payload in ({"success": True}, {"success": True, "data": None}):
        reading = RailRadarClient.parse_station_board("BSL", payload)
        assert reading.source is RailDataSource.UNAVAILABLE, payload
        assert reading.available is False


def test_genuinely_empty_train_list_is_still_live():
    """The counterpart: an explicit empty list really does mean no trains."""
    reading = RailRadarClient.parse_station_board("MMR", {"success": True, "data": {"trains": []}})
    assert reading.source is RailDataSource.LIVE


def test_null_navigational_status_does_not_crash():
    """Regression: int(None) killed the collector loop and forced a reconnect."""
    raw = fixture("ais_position_report.json")
    raw["Message"]["PositionReport"]["NavigationalStatus"] = None
    state = parse_ais_message(raw)
    assert state is not None
    assert state.nav_status == 15  # AIS "undefined"


def test_ais_name_padding_is_stripped():
    """Regression: AIS pads fixed-width fields with '@'."""
    raw = fixture("ais_position_report.json")
    raw["MetaData"]["ShipName"] = "MAERSK KOLKATA@@@@@@"
    assert parse_ais_message(raw).name == "MAERSK KOLKATA"


def test_blank_name_becomes_none():
    raw = fixture("ais_position_report.json")
    raw["MetaData"]["ShipName"] = "@@@@@@@@"
    assert parse_ais_message(raw).name is None


def test_ingest_never_raises_on_garbage(monkeypatch):
    from app.services import live_port

    monkeypatch.setattr(live_port.settings, "AISSTREAM_API_KEY", "test-key", raising=False)
    collector = AisCollector()
    for junk in (
        {},
        {"MessageType": "PositionReport", "Message": {"PositionReport": None}},
        {"MessageType": "PositionReport", "Message": {"PositionReport": {"UserID": "abc"}}},
    ):
        assert collector.ingest(junk) is False


def test_early_running_train_scores_as_clear():
    """Negative delayMinutes means the train is ahead of schedule."""
    r = [StationCongestion("X", RailDataSource.LIVE, train_count=1, mean_delay_minutes=-10)]
    assert delay_to_congestion_score(r) == 100.0


def test_port_congestion_is_monotonic():
    vals = [anchorage_to_congestion_pct(a, 2) for a in range(0, 30)]
    assert all(a <= b for a, b in zip(vals, vals[1:])), "more ships waiting must never score better"


def test_unreachable_provider_does_not_burn_quota(monkeypatch):
    """Regression: connection failures consumed the monthly allowance.

    On a flaky network this drained all 1,000 requests without a single
    successful call, then reported the corridor as permanently unavailable.
    """
    import asyncio

    from app.services import live_rail

    class UnreachableClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            raise live_rail.httpx.ConnectError("offline test fixture")

    monkeypatch.setattr(live_rail.httpx, "AsyncClient", UnreachableClient)

    client = RailRadarClient()
    original_key = live_rail.settings.RAILRADAR_API_KEY
    live_rail.settings.RAILRADAR_API_KEY = "test-key"
    try:
        start = client.budget.remaining
        asyncio.run(client.fetch_station("BSL"))  # httpx stub raises HTTPError
        assert client.budget.remaining == start, "unreachable provider must be refunded"
    finally:
        live_rail.settings.RAILRADAR_API_KEY = original_key


def test_rate_limited_response_is_not_refunded():
    """A 429 means the provider DID see and count the request."""
    client = RailRadarClient()
    client.budget.spend()
    before = client.budget.remaining
    client.budget.refund()
    assert client.budget.remaining == before + 1  # refund works
    assert client.budget.remaining <= client.budget.monthly_limit


def test_refund_cannot_go_negative():
    client = RailRadarClient()
    for _ in range(5):
        client.budget.refund()
    assert client.budget.remaining == client.budget.monthly_limit
