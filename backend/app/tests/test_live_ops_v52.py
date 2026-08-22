from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.api.v1.live_ops import event_response
from app.models.live_ops import OperationalEvent, ProviderObservation
from app.schemas.live_ops import (
    LiveDataEnvelope,
    ObservationLocation,
    ObservationQuality,
    ShipmentPositionCreate,
)
from app.services.event_engine import events_from_observation
from app.services.live_data import (
    CircuitBreaker,
    OpenMeteoProvider,
    classify_freshness,
    envelope_checksum,
    validate_observation,
)
from app.workers import live_ingestor


def envelope(**overrides) -> LiveDataEnvelope:
    now = datetime.now(timezone.utc)
    values = {
        "provider_key": "open_meteo",
        "provider_label": "Open-Meteo",
        "provider_version": "1.0",
        "category": "WEATHER",
        "source_type": "LIVE_PROVIDER",
        "status": "LIVE",
        "observed_at": now,
        "fetched_at": now,
        "age_seconds": 0,
        "freshness": "FRESH",
        "cache_hit": False,
        "quality": ObservationQuality(valid=True, completeness=1.0),
        "location": ObservationLocation(latitude=21.1458, longitude=79.0882),
        "data": {"rain": 0.0, "visibility": 10000, "wind_gusts_10m": 3.0},
        "raw_source_state": "LIVE",
        "request_id": str(uuid4()),
    }
    values.update(overrides)
    return LiveDataEnvelope(**values)


def test_freshness_has_fresh_aging_and_stale_boundaries() -> None:
    now = datetime.now(timezone.utc)
    assert classify_freshness(now - timedelta(seconds=30), 60, 120)[0] == "FRESH"
    assert classify_freshness(now - timedelta(seconds=90), 60, 120)[0] == "AGING"
    assert classify_freshness(now - timedelta(seconds=180), 60, 120)[0] == "STALE"


def test_future_observation_is_invalid() -> None:
    item = envelope(observed_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    assert "future" in validate_observation(item)[0]


def test_checksum_ignores_fetch_attempt_identity() -> None:
    first = envelope(request_id="first", fetched_at=datetime.now(timezone.utc))
    second = first.model_copy(
        update={
            "request_id": "second",
            "fetched_at": first.fetched_at + timedelta(seconds=2),
            "data": {**first.data, "provider_latency_ms": 712.0},
        }
    )
    assert envelope_checksum(first) == envelope_checksum(second)


def test_unavailable_attempts_keep_distinct_audit_checksums() -> None:
    first = envelope(
        status="UNAVAILABLE",
        observed_at=None,
        fetched_at=datetime.now(timezone.utc),
        data={},
        quality=ObservationQuality(
            valid=False, completeness=0, validation_errors=["TimeoutError"]
        ),
    )
    second = first.model_copy(
        update={"fetched_at": first.fetched_at + timedelta(seconds=10)}
    )
    assert envelope_checksum(first) != envelope_checksum(second)


def test_circuit_breaker_opens_and_half_opens() -> None:
    breaker = CircuitBreaker(threshold=2, cooldown_seconds=1)
    breaker.failure()
    assert breaker.state == "CLOSED"
    breaker.failure()
    assert breaker.state == "OPEN"
    breaker.opened_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    assert breaker.state == "HALF_OPEN"
    breaker.success()
    assert breaker.state == "CLOSED"


@pytest.mark.asyncio
async def test_provider_failure_is_truthfully_unavailable(monkeypatch) -> None:
    provider = OpenMeteoProvider()

    async def fail(_context):
        raise TimeoutError("offline")

    monkeypatch.setattr(provider, "_fetch_once", fail)
    result = await provider.fetch({"location": {"latitude": 21.1, "longitude": 79.1}})
    assert result.status == "UNAVAILABLE"
    assert result.quality.valid is False


@pytest.mark.asyncio
async def test_invalid_provider_payload_counts_as_circuit_failure(monkeypatch) -> None:
    provider = OpenMeteoProvider()

    async def future_observation(_context):
        return (
            {"temperature_2m": 25, "weather_code": 0, "wind_speed_10m": 3},
            datetime.now(timezone.utc) + timedelta(minutes=10),
        )

    monkeypatch.setattr(provider, "_fetch_once", future_observation)
    result = await provider.fetch(
        {"location": {"latitude": 21.1, "longitude": 79.1}}
    )
    assert result.status == "INVALID"
    assert provider.breaker.failures == 1


@pytest.mark.asyncio
async def test_http_429_is_classified_as_rate_limited(monkeypatch) -> None:
    provider = OpenMeteoProvider()
    request = httpx.Request("GET", "https://provider.invalid")
    response = httpx.Response(429, request=request)

    async def rate_limited(_context):
        raise httpx.HTTPStatusError(
            "rate limited", request=request, response=response
        )

    monkeypatch.setattr(provider, "_fetch_once", rate_limited)
    result = await provider.fetch(
        {"location": {"latitude": 21.1, "longitude": 79.1}}
    )
    assert result.status == "RATE_LIMITED"
    assert result.raw_source_state == "RATE_LIMITED"


def test_weather_event_thresholds_are_deterministic() -> None:
    observation = ProviderObservation(
        provider_key="open_meteo",
        observation_type="WEATHER",
        fetched_at=datetime.now(timezone.utc),
        freshness_state="FRESH",
        raw_source_state="LIVE",
        normalized_payload={},
        payload_checksum="a" * 64,
        valid=True,
    )
    item = envelope(data={"rain": 8.0, "visibility": 900, "wind_gusts_10m": 55.0})
    assert {event.event_type for event in events_from_observation(observation, item)} == {
        "HEAVY_RAIN",
        "LOW_VISIBILITY",
        "HIGH_WIND",
    }


def test_unavailable_provider_creates_medium_not_critical_event() -> None:
    observation = ProviderObservation(
        provider_key="open_meteo",
        observation_type="WEATHER",
        fetched_at=datetime.now(timezone.utc),
        freshness_state="UNKNOWN",
        raw_source_state="UNAVAILABLE",
        normalized_payload={},
        payload_checksum="b" * 64,
        valid=False,
    )
    item = envelope(
        status="UNAVAILABLE",
        source_type="UNAVAILABLE",
        raw_source_state="UNAVAILABLE",
        quality=ObservationQuality(
            valid=False, completeness=0, validation_errors=["provider timeout"]
        ),
    )
    event = events_from_observation(observation, item)[0]
    assert event.event_type == "PROVIDER_UNAVAILABLE"
    assert event.severity == "MEDIUM"


def test_global_provider_event_is_read_only_for_operator() -> None:
    now = datetime.now(timezone.utc)
    event = OperationalEvent(
        id=uuid4(),
        user_id=None,
        event_type="PROVIDER_UNAVAILABLE",
        severity="MEDIUM",
        state="OPEN",
        title="Provider unavailable",
        detail="No current observation was supplied.",
        observed_at=now,
        created_at=now,
    )

    assert event_response(event).actionable is False
    event.user_id = "operator-1"
    assert event_response(event).actionable is True


def test_position_input_cannot_claim_a_verified_rail_feed() -> None:
    with pytest.raises(ValidationError):
        ShipmentPositionCreate(
            latitude=21.1458,
            longitude=79.0882,
            source_type="RAIL_FEED",
            observed_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_noaa_current_object_row_shape(monkeypatch) -> None:
    from app.services import live_data

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [{"time_tag": "2026-08-22T06:00:00", "Kp": 0.67}]

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(live_data.httpx, "AsyncClient", Client)
    payload, observed = await live_data.NoaaKpProvider()._fetch_once({})

    assert payload["kp_index"] == 0.67
    assert observed == datetime(2026, 8, 22, 6, 0)


@pytest.mark.asyncio
async def test_retention_failure_is_contained_and_retryable(monkeypatch) -> None:
    class FakeDb:
        def __init__(self) -> None:
            self.rollbacks = 0

        async def rollback(self) -> None:
            self.rollbacks += 1

    async def fail(_db):
        raise RuntimeError("retention database unavailable")

    monkeypatch.setattr(live_ingestor, "_last_retention_at", None)
    monkeypatch.setattr(live_ingestor, "purge_live_observations", fail)
    db = FakeDb()

    result = await live_ingestor._purge_retention_if_due(db)

    assert result == {"retention_failures": 1}
    assert db.rollbacks == 1
    assert live_ingestor._last_retention_at is None
