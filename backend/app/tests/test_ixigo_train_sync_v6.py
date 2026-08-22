from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.services.ixigo_sync import IxigoPartnerProvider
from app.workers.train_synchronizer import sync_once


@pytest.mark.asyncio
async def test_ixigo_is_fail_closed_without_authorized_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "IXIGO_SYNC_ENABLED", False)
    monkeypatch.setattr(settings, "IXIGO_TRAIN_STATUS_URL", "")
    monkeypatch.setattr(settings, "IXIGO_API_KEY", "")

    result = await IxigoPartnerProvider().fetch({"train_number": "12345"})

    assert result.status == "AUTH_REQUIRED"
    assert result.source_type == "UNAVAILABLE"
    assert result.quality.valid is False
    assert "partner endpoint/key" in result.quality.validation_errors[0]


@pytest.mark.asyncio
async def test_ixigo_rejects_non_https_partner_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(settings, "IXIGO_SYNC_ENABLED", True)
    monkeypatch.setattr(
        settings, "IXIGO_TRAIN_STATUS_URL", "http://consumer-endpoint.invalid/status"
    )
    monkeypatch.setattr(settings, "IXIGO_API_KEY", "configured-but-not-exposed")

    result = await IxigoPartnerProvider().fetch({"train_number": "12345"})

    assert result.status == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_ixigo_partner_payload_is_whitelisted_and_normalized(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "IXIGO_SYNC_ENABLED", True)
    monkeypatch.setattr(
        settings, "IXIGO_TRAIN_STATUS_URL", "https://partner.example/status"
    )
    monkeypatch.setattr(settings, "IXIGO_API_KEY", "secret-value")
    observed = datetime.now(timezone.utc).replace(microsecond=0)

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "data": {
                    "observed_at": observed.isoformat(),
                    "status": "RUNNING",
                    "current_station": "Nagpur",
                    "station_code": "NGP",
                    "delay": 12,
                    "lat": 21.1458,
                    "lon": 79.0882,
                    "passenger_name": "must not persist",
                    "api_key": "must not persist",
                }
            }

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def get(self, *_args, **_kwargs) -> Response:
            return Response()

    monkeypatch.setattr("app.services.ixigo_sync.httpx.AsyncClient", Client)
    payload, timestamp = await IxigoPartnerProvider()._fetch_once(
        {"train_number": "12345"}
    )

    assert timestamp == observed
    assert payload["delay_minutes"] == 12
    assert payload["station_code"] == "NGP"
    assert "passenger_name" not in payload
    assert "api_key" not in payload


@pytest.mark.asyncio
async def test_train_sync_worker_is_stably_disabled_without_partner_access(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "IXIGO_SYNC_ENABLED", False)
    assert await sync_once() == {
        "synchronized": 0,
        "skipped_disabled": 1,
        "failures": 0,
    }


@pytest.mark.asyncio
async def test_train_sync_worker_pages_past_first_250(monkeypatch) -> None:
    from app.workers import train_synchronizer

    pages = [list(range(250)), [250]]
    processed: list[int] = []

    class ScalarResult:
        def __init__(self, values: list[int]) -> None:
            self.values = values

        def all(self) -> list[int]:
            return self.values

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def scalars(self, _statement) -> ScalarResult:
            return ScalarResult(pages.pop(0) if pages else [])

    async def record(schedule_id: int) -> bool:
        processed.append(schedule_id)
        return True

    monkeypatch.setattr(settings, "IXIGO_SYNC_ENABLED", True)
    monkeypatch.setattr(train_synchronizer, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(train_synchronizer, "_sync_one", record)

    result = await train_synchronizer.sync_once()

    assert result == {"synchronized": 251, "skipped_disabled": 0, "failures": 0}
    assert len(processed) == 251
