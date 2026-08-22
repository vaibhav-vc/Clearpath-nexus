from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.live_ops import TrainSyncState
from app.models.provenance import LineageEdge, ProvenanceRecord
from app.models.route import TrainSchedule
from app.schemas.live_ops import LiveDataEnvelope, ObservationQuality
from app.services.live_data import (
    LiveDataProvider,
    cache_latest,
    persist_envelope,
    utc_now,
)


class IxigoPartnerProvider(LiveDataProvider):
    """Authorized partner-gateway adapter; never targets ixigo consumer internals."""

    provider_key = "ixigo_partner"
    provider_label = "ixigo authorized partner gateway"
    provider_version = "1.0"
    category = "PASSENGER_TRAIN_STATUS"
    fresh_seconds = 300
    stale_seconds = 1800
    attribution = "ixigo passenger train information (authorized access required)"
    limitations = [
        "Optional third-party passenger information; not freight operations authority.",
        "Not railway signalling, dispatch control, or a guaranteed running position.",
        "Requires a separately authorized ixigo/partner endpoint and API key.",
    ]

    def _configured(self) -> bool:
        parsed = urlparse(settings.IXIGO_TRAIN_STATUS_URL)
        return bool(
            settings.IXIGO_SYNC_ENABLED
            and settings.IXIGO_API_KEY
            and parsed.scheme == "https"
            and parsed.hostname
        )

    async def fetch(self, context: dict[str, Any]) -> LiveDataEnvelope:
        if not self._configured():
            return self.unavailable(
                "authorized ixigo partner endpoint/key is not configured",
                str(uuid4()),
                utc_now(),
                status="AUTH_REQUIRED",
            )
        return await super().fetch(context)

    async def _fetch_once(
        self, context: dict[str, Any]
    ) -> tuple[dict[str, Any], datetime | None]:
        train_number = str(context.get("train_number", "")).strip()
        if not train_number or len(train_number) > 30:
            raise ValueError("valid train_number is required")
        async with httpx.AsyncClient(
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                settings.IXIGO_TRAIN_STATUS_URL,
                params={"train_number": train_number},
                headers={
                    "x-api-key": settings.IXIGO_API_KEY,
                    "Accept": "application/json",
                    "User-Agent": "ClearPath-Nexus/6.0",
                },
            )
            response.raise_for_status()
            if len(getattr(response, "content", b"")) > 1_000_000:
                raise ValueError("partner response exceeds one megabyte")
            body = response.json()
        if not isinstance(body, dict):
            raise ValueError("partner response must be a JSON object")
        raw = body.get("data", body)
        if not isinstance(raw, dict):
            raise ValueError("partner response data must be an object")
        timestamp = raw.get("observed_at") or raw.get("updated_at") or raw.get(
            "last_updated"
        )
        if not timestamp:
            raise ValueError("partner response has no observation timestamp")
        observed_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))

        delay = raw.get("delay_minutes", raw.get("delay"))
        latitude = raw.get("latitude", raw.get("lat"))
        longitude = raw.get("longitude", raw.get("lon"))
        def optional_text(key: str, fallback: str | None = None, limit: int = 160):
            value = raw.get(key, raw.get(fallback) if fallback else None)
            if value is None:
                return None
            if not isinstance(value, (str, int, float)):
                raise ValueError(f"{key} must be scalar text")
            return str(value)[:limit]

        normalized: dict[str, Any] = {
            "train_number": train_number,
            "running_status": optional_text("running_status", "status", 80),
            "current_station": optional_text("current_station", limit=160),
            "station_code": optional_text("station_code", limit=20),
            "delay_minutes": float(delay) if delay is not None else None,
            "latitude": float(latitude) if latitude is not None else None,
            "longitude": float(longitude) if longitude is not None else None,
            "scheduled_arrival": optional_text("scheduled_arrival", limit=80),
            "estimated_arrival": optional_text("estimated_arrival", limit=80),
        }
        if normalized["delay_minutes"] is not None and not -240 <= normalized[
            "delay_minutes"
        ] <= 10000:
            raise ValueError("delay_minutes outside accepted range")
        if normalized["latitude"] is not None and not -90 <= normalized[
            "latitude"
        ] <= 90:
            raise ValueError("latitude outside accepted range")
        if normalized["longitude"] is not None and not -180 <= normalized[
            "longitude"
        ] <= 180:
            raise ValueError("longitude outside accepted range")
        return normalized, observed_at


ixigo_partner_provider = IxigoPartnerProvider()


async def synchronize_schedule(
    db: AsyncSession,
    schedule: TrainSchedule,
    user_id: str,
) -> TrainSyncState:
    """Fetch, normalize, persist SourceLine, and update the owned sync projection."""
    envelope = await ixigo_partner_provider.fetch(
        {"train_number": schedule.train_code}
    )
    observation = await persist_envelope(
        db,
        envelope,
        "PASSENGER_TRAIN_STATUS",
        "TRAIN_SCHEDULE",
        str(schedule.id),
        user_id=user_id,
    )
    await cache_latest(envelope, f"TRAIN_STATUS:{schedule.id}")
    state = await db.scalar(
        select(TrainSyncState).where(TrainSyncState.schedule_id == schedule.id)
    )
    if state is None:
        state = TrainSyncState(
            user_id=user_id,
            schedule_id=schedule.id,
            provider_key=ixigo_partner_provider.provider_key,
            train_number=schedule.train_code,
            fetched_at=envelope.fetched_at,
            normalized_payload={},
        )
        db.add(state)
    data = envelope.data
    state.user_id = user_id
    state.train_number = schedule.train_code
    state.status = envelope.status
    state.freshness = envelope.freshness
    state.current_station = data.get("current_station")
    state.station_code = data.get("station_code")
    state.delay_minutes = data.get("delay_minutes")
    state.latitude = data.get("latitude")
    state.longitude = data.get("longitude")
    state.observed_at = envelope.observed_at
    state.fetched_at = envelope.fetched_at
    state.normalized_payload = data
    state.last_error = (
        None
        if envelope.quality.valid
        else "; ".join(envelope.quality.validation_errors)
    )
    # An owner-scoped record links the globally reusable provider observation
    # to this operator's schedule without copying secrets or raw provider data.
    owner_record = ProvenanceRecord(
        user_id=user_id,
        entity_type="train_synchronization",
        entity_key=f"schedule:{schedule.id}:{envelope.request_id}",
        decision_input_role="SUPPLEMENTARY_PASSENGER_TRAIN_STATUS",
        canonical_source_type=envelope.source_type,
        raw_source_state=envelope.raw_source_state,
        observed_at=envelope.observed_at,
        fetched_at=envelope.fetched_at,
        freshness_state=envelope.freshness,
        freshness_seconds=envelope.age_seconds,
        cache_hit=envelope.cache_hit,
        used_in_decision=False,
        excluded_reason=(
            "Supplementary passenger signal; never authoritative freight control input"
            if envelope.quality.valid
            else state.last_error
        ),
        availability_state=envelope.status,
        completeness=envelope.quality.completeness,
        request_id=envelope.request_id,
        value_summary={
            "schedule_id": str(schedule.id),
            "train_number": schedule.train_code,
            "status": envelope.status,
        },
        metadata_json={"limitations": envelope.limitations},
    )
    db.add(owner_record)
    await db.flush()
    state.provenance_record_id = owner_record.id
    if observation is not None and observation.provenance_record_id is not None:
        db.add(
            LineageEdge(
                parent_record_id=observation.provenance_record_id,
                child_record_id=owner_record.id,
                relationship="REFERENCES",
            )
        )
    await db.commit()
    await db.refresh(state)
    return state


def unavailable_ixigo_envelope() -> LiveDataEnvelope:
    """Stable helper used by UI/status checks without making a network request."""
    return LiveDataEnvelope(
        provider_key=ixigo_partner_provider.provider_key,
        provider_label=ixigo_partner_provider.provider_label,
        provider_version=ixigo_partner_provider.provider_version,
        category=ixigo_partner_provider.category,
        source_type="UNAVAILABLE",
        status="AUTH_REQUIRED",
        observed_at=None,
        fetched_at=utc_now(),
        age_seconds=None,
        freshness="UNKNOWN",
        cache_hit=False,
        quality=ObservationQuality(
            valid=False,
            completeness=0,
            validation_errors=["authorized partner access is not configured"],
        ),
        data={},
        raw_source_state="AUTH_REQUIRED",
        request_id=str(uuid4()),
        attribution=ixigo_partner_provider.attribution,
        limitations=ixigo_partner_provider.limitations,
    )
