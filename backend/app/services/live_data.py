from __future__ import annotations

import asyncio
import hashlib
import json
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.observability import provider_status
from app.models.live_ops import ProviderObservation
from app.models.provenance import DataSource, ProvenanceRecord
from app.schemas.live_ops import LiveDataEnvelope, ObservationLocation, ObservationQuality


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def classify_freshness(observed_at: datetime | None, fresh_seconds: int, stale_seconds: int) -> tuple[str, int | None]:
    observed = ensure_utc(observed_at)
    if observed is None:
        return "UNKNOWN", None
    age = max(0, int((utc_now() - observed).total_seconds()))
    if age <= fresh_seconds:
        return "FRESH", age
    if age <= stale_seconds:
        return "AGING", age
    return "STALE", age


def validate_observation(envelope: LiveDataEnvelope) -> list[str]:
    errors: list[str] = []
    observed = ensure_utc(envelope.observed_at)
    if observed and observed > utc_now() + timedelta(minutes=5):
        errors.append("observation timestamp is more than five minutes in the future")
    if envelope.location:
        if not -90 <= envelope.location.latitude <= 90:
            errors.append("latitude outside valid range")
        if not -180 <= envelope.location.longitude <= 180:
            errors.append("longitude outside valid range")
    for key, value in envelope.data.items():
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            errors.append(f"{key} is not finite")
    return errors


class CircuitBreaker:
    def __init__(self, threshold: int = 3, cooldown_seconds: int = 120) -> None:
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at: datetime | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "CLOSED"
        if utc_now() >= self.opened_at + timedelta(seconds=self.cooldown_seconds):
            return "HALF_OPEN"
        return "OPEN"

    def allow(self) -> bool:
        return self.state != "OPEN"

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = utc_now()


class LiveDataProvider(ABC):
    provider_key: str
    provider_label: str
    provider_version = "1.0"
    category: str
    fresh_seconds: int
    stale_seconds: int
    attribution: str
    limitations: list[str]

    def __init__(self) -> None:
        self.breaker = CircuitBreaker(settings.PROVIDER_FAILURE_THRESHOLD, settings.PROVIDER_CIRCUIT_COOLDOWN_SECONDS)

    @abstractmethod
    async def _fetch_once(self, context: dict[str, Any]) -> tuple[dict[str, Any], datetime | None]: ...

    async def fetch(self, context: dict[str, Any]) -> LiveDataEnvelope:
        request_id = str(uuid4())
        location = context.get("location")
        if not self.breaker.allow():
            return self.unavailable(
                "provider circuit is open", request_id, utc_now(), location
            )
        started = perf_counter()
        last_error: Exception | None = None
        for attempt in range(settings.PROVIDER_MAX_RETRIES + 1):
            try:
                payload, observed_at = await self._fetch_once(context)
                fetched_at = utc_now()
                freshness, age = classify_freshness(observed_at, self.fresh_seconds, self.stale_seconds)
                status = "LIVE" if freshness == "FRESH" else freshness
                envelope = LiveDataEnvelope(
                    provider_key=self.provider_key, provider_label=self.provider_label,
                    provider_version=self.provider_version, category=self.category,
                    source_type="LIVE_PROVIDER", status=status, observed_at=ensure_utc(observed_at),
                    fetched_at=fetched_at, age_seconds=age, freshness=freshness, cache_hit=False,
                    quality=ObservationQuality(valid=True, completeness=1.0),
                    location=ObservationLocation(**location) if location else None, data=payload,
                    raw_source_state="LIVE", request_id=request_id, attribution=self.attribution,
                    limitations=self.limitations,
                )
                errors = validate_observation(envelope)
                if errors:
                    envelope.status = "INVALID"
                    envelope.quality = ObservationQuality(valid=False, completeness=1.0, validation_errors=errors)
                    self.breaker.failure()
                    provider_status.record_failure(self.provider_key)
                else:
                    self.breaker.success()
                    provider_status.record_success(self.provider_key)
                envelope.data["provider_latency_ms"] = round((perf_counter() - started) * 1000, 2)
                return envelope
            except Exception as exc:
                last_error = exc
                if attempt < settings.PROVIDER_MAX_RETRIES:
                    await asyncio.sleep((0.25 * (2**attempt)) + random.uniform(0, 0.15))
        self.breaker.failure()
        provider_status.record_failure(self.provider_key)
        status = "UNAVAILABLE"
        if isinstance(last_error, httpx.HTTPStatusError):
            if last_error.response.status_code == 429:
                status = "RATE_LIMITED"
            elif last_error.response.status_code in {401, 403}:
                status = "AUTH_REQUIRED"
        return self.unavailable(
            type(last_error).__name__ if last_error else "unknown failure",
            request_id,
            utc_now(),
            location,
            status=status,
        )

    def unavailable(
        self,
        detail: str,
        request_id: str,
        fetched_at: datetime,
        location: dict[str, float] | None = None,
        *,
        status: str = "UNAVAILABLE",
    ) -> LiveDataEnvelope:
        return LiveDataEnvelope(
            provider_key=self.provider_key, provider_label=self.provider_label,
            provider_version=self.provider_version, category=self.category,
            source_type="UNAVAILABLE", status=status, observed_at=None, fetched_at=fetched_at,
            age_seconds=None, freshness="UNKNOWN", cache_hit=False,
            quality=ObservationQuality(valid=False, completeness=0, validation_errors=[detail]),
            location=ObservationLocation(**location) if location else None, data={},
            raw_source_state=status, request_id=request_id, attribution=self.attribution,
            limitations=self.limitations,
        )

    async def health(self) -> dict[str, Any]:
        return {"provider_key": self.provider_key, "circuit_state": self.breaker.state, "consecutive_failures": self.breaker.failures}


class OpenMeteoProvider(LiveDataProvider):
    provider_key = "open_meteo"
    provider_label = "Open-Meteo"
    category = "WEATHER"
    fresh_seconds = 900
    stale_seconds = 3600
    attribution = "Weather data by Open-Meteo"
    limitations = ["Best-effort public forecast API; no commercial production SLA is implied."]

    async def _fetch_once(self, context: dict[str, Any]) -> tuple[dict[str, Any], datetime | None]:
        location = context["location"]
        params = {
            "latitude": location["latitude"], "longitude": location["longitude"], "timezone": "UTC",
            "current": "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility",
        }
        async with httpx.AsyncClient(timeout=settings.PROVIDER_TIMEOUT_SECONDS) as client:
            response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            response.raise_for_status()
            current = response.json().get("current")
        if not isinstance(current, dict) or "time" not in current:
            raise ValueError("missing current weather object or timestamp")
        required = {"temperature_2m", "weather_code", "wind_speed_10m"}
        if not required.issubset(current):
            raise ValueError("missing required weather variables")
        observed = datetime.fromisoformat(str(current["time"]).replace("Z", "+00:00"))
        return current, observed


class NoaaKpProvider(LiveDataProvider):
    provider_key = "noaa_swpc"
    provider_label = "NOAA Space Weather Prediction Center"
    category = "SPACE_WEATHER"
    fresh_seconds = 1800
    stale_seconds = 10800
    attribution = "NOAA Space Weather Prediction Center"
    limitations = ["Supplemental environmental intelligence; not railway signalling authority."]

    async def _fetch_once(self, context: dict[str, Any]) -> tuple[dict[str, Any], datetime | None]:
        async with httpx.AsyncClient(timeout=settings.PROVIDER_TIMEOUT_SECONDS) as client:
            response = await client.get(settings.NOAA_SPACE_WEATHER_FEED_URL)
            response.raise_for_status()
            rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise ValueError("malformed NOAA Kp product")
        latest = rows[-1]
        if isinstance(latest, dict):
            timestamp = latest.get("time_tag")
            kp_value = latest.get("Kp")
        elif isinstance(latest, list) and len(latest) >= 2:
            timestamp, kp_value = latest[0], latest[1]
        else:
            raise ValueError("malformed NOAA Kp row")
        if timestamp is None or kp_value is None:
            raise ValueError("NOAA Kp row is missing timestamp or value")
        observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return {"kp_index": float(kp_value), "product_timestamp": timestamp}, observed


def envelope_checksum(envelope: LiveDataEnvelope) -> str:
    canonical = json.dumps(
        {
            "provider_key": envelope.provider_key,
            "observed_at": envelope.observed_at.isoformat() if envelope.observed_at else None,
            "location": envelope.location.model_dump() if envelope.location else None,
            "status": envelope.status,
            # Provider failures have no observation timestamp or payload. Include
            # the fetch time so consecutive outages remain auditable rather than
            # being deduplicated forever as one empty observation.
            "failure_fetched_at": (
                envelope.fetched_at.isoformat() if envelope.observed_at is None else None
            ),
            "validation_errors": envelope.quality.validation_errors,
            "data": {
                key: value
                for key, value in envelope.data.items()
                if key != "provider_latency_ms"
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def persist_envelope(
    db: AsyncSession,
    envelope: LiveDataEnvelope,
    observation_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
) -> ProviderObservation | None:
    checksum = envelope_checksum(envelope)
    duplicate = await db.scalar(
        select(ProviderObservation).where(
            ProviderObservation.payload_checksum == checksum,
            ProviderObservation.observation_type == observation_type,
            (
                ProviderObservation.user_id.is_(None)
                if user_id is None
                else ProviderObservation.user_id == user_id
            ),
            (
                ProviderObservation.entity_type.is_(None)
                if entity_type is None
                else ProviderObservation.entity_type == entity_type
            ),
            (
                ProviderObservation.entity_id.is_(None)
                if entity_id is None
                else ProviderObservation.entity_id == entity_id
            ),
        )
    )
    if duplicate:
        return None
    source = await db.scalar(select(DataSource).where(DataSource.key == envelope.provider_key))
    provenance = ProvenanceRecord(
        user_id="SYSTEM", source_id=source.id if source else None, entity_type="provider_observation",
        entity_key=(
            f"{envelope.provider_key}:{observation_type}:"
            f"{entity_id or 'global'}:{checksum[:12]}"
        ),
        decision_input_role="LIVE_OPERATIONAL_INPUT", canonical_source_type=envelope.source_type,
        raw_source_state=envelope.raw_source_state, observed_at=envelope.observed_at,
        fetched_at=envelope.fetched_at, freshness_state=envelope.freshness,
        freshness_seconds=envelope.age_seconds, cache_hit=envelope.cache_hit,
        used_in_decision=False, excluded_reason=None if envelope.quality.valid else "; ".join(envelope.quality.validation_errors),
        availability_state=envelope.status, completeness=envelope.quality.completeness,
        request_id=envelope.request_id, checksum=checksum,
        value_summary={"observation_type": observation_type, "status": envelope.status},
        metadata_json={"provider_version": envelope.provider_version, "limitations": envelope.limitations},
    )
    db.add(provenance)
    await db.flush()
    observation = ProviderObservation(
        user_id=user_id,
        provider_id=source.id if source else None, provider_key=envelope.provider_key,
        observation_type=observation_type, entity_type=entity_type, entity_id=entity_id,
        latitude=envelope.location.latitude if envelope.location else None,
        longitude=envelope.location.longitude if envelope.location else None,
        observed_at=envelope.observed_at, fetched_at=envelope.fetched_at,
        freshness_state=envelope.freshness, raw_source_state=envelope.raw_source_state,
        normalized_payload=envelope.model_dump(mode="json"), payload_checksum=checksum,
        valid=envelope.quality.valid, validation_error="; ".join(envelope.quality.validation_errors) or None,
        provenance_record_id=provenance.id,
    )
    db.add(observation)
    await db.flush()
    return observation


async def cache_latest(envelope: LiveDataEnvelope, observation_type: str) -> None:
    if not envelope.quality.valid:
        return
    redis: Redis | None = None
    try:
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        await redis.setex(f"live:{envelope.provider_key}:{observation_type}", settings.LIVE_OBSERVATION_CACHE_SECONDS, envelope.model_dump_json())
    except Exception:
        return
    finally:
        if redis is not None:
            await redis.aclose()


PROVIDERS: dict[str, LiveDataProvider] = {"open_meteo": OpenMeteoProvider(), "noaa_swpc": NoaaKpProvider()}
