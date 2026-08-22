from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.observability import provider_status

logger = logging.getLogger(__name__)

UNAVAILABLE_WEATHER = {"status": "unavailable", "source": "provider-unavailable"}
UNAVAILABLE_KP = {
    "status": "unavailable",
    "source": "provider-unavailable",
    "kp_index": None,
    "alert_level": "UNKNOWN",
    "issue_datetime": None,
}


def _with_provenance(
    payload: dict[str, Any],
    *,
    provider: str,
    raw_state: str,
    observed_at: str | None = None,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Attach decision-safe provider metadata; never include request credentials."""
    result = dict(payload)
    result["_provenance"] = {
        "provider": provider,
        "raw_state": raw_state,
        "observed_at": observed_at,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
    }
    return result


class SpaceWeatherService:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
        return self._redis

    async def _cache_get(self, key: str) -> dict[str, Any] | None:
        try:
            redis = await self._get_redis()
            raw = await redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _cache_set(self, key: str, payload: dict[str, Any], ttl: int = 900) -> None:
        try:
            redis = await self._get_redis()
            await redis.set(key, json.dumps(payload), ex=ttl)
        except Exception:
            pass

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def fetch_route_environmental_risks(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch configured weather data, falling back to Open-Meteo."""
        cache_key = f"weather:{lat:.2f}:{lon:.2f}"
        cached = await self._cache_get(cache_key)
        if cached:
            cached_meta = cached.get("_provenance", {})
            return _with_provenance(
                {k: v for k, v in cached.items() if k != "_provenance"},
                provider=cached_meta.get("provider", "open_meteo"),
                raw_state="CACHED",
                observed_at=cached_meta.get("observed_at"),
                fetched_at=cached_meta.get("fetched_at"),
            )

        if not settings.OPENWEATHER_API_KEY:
            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,visibility"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    current = resp.json().get("current", {})
                    required = {
                        "temperature_2m",
                        "relative_humidity_2m",
                        "weather_code",
                        "wind_speed_10m",
                        "visibility",
                    }
                    if not required.issubset(current):
                        raise ValueError("Open-Meteo response is missing current weather fields")
                    owm_data = {
                        "wind": {
                            "speed": round(current.get("wind_speed_10m", 0) / 3.6, 2)  # km/h to m/s
                        },
                        "main": {
                            "temp": current.get("temperature_2m", 25.0),
                            "visibility": current.get("visibility", 10000),
                            "humidity": current.get("relative_humidity_2m", 50),
                        },
                        "weather": [
                            {
                                "id": 500 if int(current.get("weather_code", 0)) >= 51 else 800,
                                "main": "Precipitation"
                                if int(current.get("weather_code", 0)) >= 51
                                else "Clear",
                                "description": "precipitation"
                                if int(current.get("weather_code", 0)) >= 51
                                else "clear sky",
                            }
                        ],
                    }
                    owm_data = _with_provenance(
                        owm_data,
                        provider="open_meteo",
                        raw_state="LIVE",
                        observed_at=current.get("time"),
                    )
                    await self._cache_set(cache_key, owm_data)
                    provider_status.record_success("open_meteo")
                    return owm_data
            except Exception as exc:
                provider_status.record_failure("open_meteo")
                logger.warning("Open-Meteo weather fetch failed: %s", exc)
                return _with_provenance(
                    UNAVAILABLE_WEATHER, provider="open_meteo", raw_state="UNAVAILABLE"
                )

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": settings.OPENWEATHER_API_KEY, "units": "metric"}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = _with_provenance(
                    resp.json(),
                    provider="openweather",
                    raw_state="LIVE",
                    observed_at=(
                        datetime.fromtimestamp(resp.json()["dt"], tz=timezone.utc).isoformat()
                        if resp.json().get("dt")
                        else None
                    ),
                )
                await self._cache_set(cache_key, data)
                provider_status.record_success("openweather")
                return data
        except Exception as exc:
            provider_status.record_failure("openweather")
            logger.warning("Weather fetch failed: %s", exc)
            cached = await self._cache_get(cache_key)
        if cached:
            cached_meta = cached.get("_provenance", {})
            return _with_provenance(
                {k: v for k, v in cached.items() if k != "_provenance"},
                provider=cached_meta.get("provider", "openweather"),
                raw_state="CACHED",
                observed_at=cached_meta.get("observed_at"),
                fetched_at=cached_meta.get("fetched_at"),
            )
        return _with_provenance(
            UNAVAILABLE_WEATHER, provider="openweather", raw_state="UNAVAILABLE"
        )

    async def fetch_route_weather_point(
        self, point_id: str, lat: float, lon: float
    ) -> dict[str, Any]:
        """Return a fully populated live weather record or an explicit unavailable result."""
        cache_key = f"route_weather:{lat:.3f}:{lon:.3f}"
        cached = await self._cache_get(cache_key)
        if cached:
            return {"id": point_id, "lat": lat, "lon": lon, "available": True, **cached}

        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
            "wind_speed_10m,wind_direction_10m,visibility,uv_index,precipitation"
            f"&latitude={lat}&longitude={lon}&timezone=auto"
        )
        required = {
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "visibility",
            "uv_index",
            "precipitation",
        }
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                current = response.json().get("current", {})
            if not required.issubset(current):
                raise ValueError("Open-Meteo response is missing route-weather fields")
            payload = {field: current[field] for field in required}
            await self._cache_set(cache_key, payload, ttl=600)
            provider_status.record_success("open_meteo")
            return {"id": point_id, "lat": lat, "lon": lon, "available": True, **payload}
        except Exception as exc:
            provider_status.record_failure("open_meteo")
            logger.warning("Route weather fetch failed for %s: %s", point_id, exc)
            return {
                "id": point_id,
                "lat": lat,
                "lon": lon,
                "available": False,
                "message": "Weather provider unavailable; do not use this record for dispatch decisions.",
            }

    async def fetch_kp_index(self) -> dict[str, Any]:
        """Parse NOAA planetary Kp-index feed."""
        cache_key = "noaa:kp_index"
        cached = await self._cache_get(cache_key)
        if cached:
            cached_meta = cached.get("_provenance", {})
            return _with_provenance(
                {k: v for k, v in cached.items() if k != "_provenance"},
                provider="noaa_swpc",
                raw_state="CACHED",
                observed_at=cached.get("issue_datetime"),
                fetched_at=cached_meta.get("fetched_at"),
            )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(settings.NOAA_SPACE_WEATHER_FEED_URL)
                resp.raise_for_status()
                rows = resp.json()
                if isinstance(rows, list) and rows:
                    latest = rows[-1]
                    if isinstance(latest, dict):
                        issue_datetime = latest.get("time_tag")
                        raw_kp = latest.get("Kp")
                    elif isinstance(latest, list) and len(latest) > 1:
                        issue_datetime = latest[0]
                        raw_kp = latest[1]
                    else:
                        raise ValueError("NOAA response is missing the latest Kp value")
                    if issue_datetime is None or raw_kp is None:
                        raise ValueError("NOAA response is missing timestamp or Kp value")
                    kp_val = int(float(raw_kp))
                    result = {
                        "kp_index": kp_val,
                        "alert_level": "WARNING" if kp_val >= 7 else "NONE",
                        "issue_datetime": str(issue_datetime),
                    }
                    result = _with_provenance(
                        result,
                        provider="noaa_swpc",
                        raw_state="LIVE",
                        observed_at=result["issue_datetime"],
                    )
                    await self._cache_set(cache_key, result)
                    provider_status.record_success("noaa_space_weather")
                    return result
        except Exception as exc:
            provider_status.record_failure("noaa_space_weather")
            logger.warning("NOAA fetch failed: %s", exc)

        cached = await self._cache_get(cache_key)
        if cached:
            cached_meta = cached.get("_provenance", {})
            return _with_provenance(
                {k: v for k, v in cached.items() if k != "_provenance"},
                provider="noaa_swpc",
                raw_state="CACHED",
                observed_at=cached.get("issue_datetime"),
                fetched_at=cached_meta.get("fetched_at"),
            )
        return _with_provenance(UNAVAILABLE_KP, provider="noaa_swpc", raw_state="UNAVAILABLE")

    def weather_to_score(
        self, weather_data: dict[str, Any], kp_data: dict[str, Any]
    ) -> tuple[float, list[str]]:
        alerts: list[str] = []
        score = 100.0

        if weather_data.get("status") == "unavailable":
            score = 50.0
            alerts.append("Weather provider unavailable — verify conditions before dispatch")
        if kp_data.get("status") == "unavailable":
            alerts.append("NOAA space-weather feed unavailable — telemetry risk is unknown")

        wind = weather_data.get("wind", {}).get("speed", 0)
        visibility = weather_data.get("main", {}).get("visibility", 10000)
        weather_codes = [w.get("id", 800) for w in weather_data.get("weather", [])]

        if any(c >= 500 for c in weather_codes):
            score -= 30
            alerts.append("Heavy precipitation detected along corridor")
        if wind > 15:
            score -= 20
            alerts.append(f"High wind speeds ({wind} m/s)")
        if visibility < 5000:
            score -= 25
            alerts.append("Reduced visibility — dust/fog risk")

        kp = kp_data.get("kp_index") or 0
        if kp >= 7:
            score -= 35
            alerts.append(f"CRITICAL: Geomagnetic Kp-index {kp} — signaling telemetry risk")
        elif kp >= 5:
            score -= 10
            alerts.append(f"Elevated Kp-index {kp}")

        return max(0.0, min(100.0, score)), alerts


space_weather_service = SpaceWeatherService()
