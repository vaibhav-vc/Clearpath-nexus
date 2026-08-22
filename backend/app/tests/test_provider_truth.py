import pytest
from datetime import datetime, timedelta, timezone

from app.services.map_conditions import fetch_map_conditions
from app.services.port_sync import compute_port_sync_score
from app.services.railradar import fetch_trains_between
from app.services.space_weather import SpaceWeatherService


def test_port_sync_score_uses_timezone_aware_window() -> None:
    score, warning = compute_port_sync_score(
        24.0,
        {
            "start_time": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
        },
    )

    assert 60.0 <= score <= 100.0
    assert warning is None


def test_unavailable_environment_is_not_scored_as_clear() -> None:
    score, alerts = SpaceWeatherService().weather_to_score(
        {"status": "unavailable"},
        {"status": "unavailable", "kp_index": None},
    )

    assert score == 50.0
    assert any("unavailable" in alert.lower() for alert in alerts)


@pytest.mark.asyncio
async def test_map_conditions_does_not_emit_all_clear_when_weather_fails(monkeypatch) -> None:
    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.map_conditions.fetch_open_meteo", unavailable)

    async def unavailable_kp():
        return {"status": "unavailable", "kp_index": None}

    monkeypatch.setattr(
        "app.services.map_conditions.space_weather_service.fetch_kp_index",
        unavailable_kp,
    )

    conditions = await fetch_map_conditions([{"lat": 21.1, "lon": 79.1, "id": "NGP"}])

    assert conditions == []


@pytest.mark.asyncio
async def test_railradar_reports_unavailable_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr("app.services.railradar.settings.RAILRADAR_API_KEY", "")

    result = await fetch_trains_between("NGP", "JNPT")

    assert result["available"] is False
    assert result["trains"] == []
