from __future__ import annotations

import math
from typing import Any

import httpx

from app.services.space_weather import space_weather_service

OPEN_METEO = (
    "https://api.open-meteo.com/v1/forecast"
    "?current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,visibility,uv_index"
    "&timezone=auto"
)


def _primary_weather_type(code: int) -> str:
    if code == 0:
        return "clear"
    if code == 1:
        return "partly_cloudy"
    if code in (2, 3):
        return "cloudy"
    if code == 45:
        return "mist"
    if code == 48:
        return "fog"
    if 51 <= code <= 57:
        return "light_rain"
    if 61 <= code <= 65:
        return "heavy_rain" if code >= 63 else "light_rain"
    if 66 <= code <= 67:
        return "sleet"
    if 71 <= code <= 77:
        return "snow"
    if 80 <= code <= 82:
        return "heavy_rain"
    if 85 <= code <= 86:
        return "snow"
    if 95 <= code <= 99:
        return "hail" if code >= 96 else "thunderstorm"
    return "cloudy"


def map_weather_to_conditions(
    data: dict[str, Any], lat: float, lon: float, point_id: str
) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    code = int(data.get("weather_code", 0))
    temp = float(data.get("temperature_2m", 20))
    humidity = float(data.get("relative_humidity_2m", 50))
    wind = float(data.get("wind_speed_10m", 0))
    visibility = float(data.get("visibility", 10000))
    uv = float(data.get("uv_index", 0))

    primary = _primary_weather_type(code)
    conditions.append(
        {
            "id": f"{point_id}-{primary}",
            "type": primary,
            "category": "weather",
            "lat": lat,
            "lon": lon,
            "reading": f"{round(temp)}°C",
        }
    )

    if wind >= 20:
        conditions.append(
            {
                "id": f"{point_id}-high_winds",
                "type": "high_winds",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{round(wind)} km/h",
            }
        )
    elif wind >= 10:
        conditions.append(
            {
                "id": f"{point_id}-strong_wind",
                "type": "strong_wind",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{round(wind)} km/h",
            }
        )

    if temp >= 35:
        conditions.append(
            {
                "id": f"{point_id}-high_temp",
                "type": "high_temp",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{round(temp)}°C",
            }
        )
    elif temp <= 5:
        conditions.append(
            {
                "id": f"{point_id}-low_temp",
                "type": "low_temp",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{round(temp)}°C",
            }
        )

    if humidity >= 85:
        conditions.append(
            {
                "id": f"{point_id}-high_humidity",
                "type": "high_humidity",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{round(humidity)}%",
            }
        )
    elif humidity <= 30:
        conditions.append(
            {
                "id": f"{point_id}-low_humidity",
                "type": "low_humidity",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{round(humidity)}%",
            }
        )

    if 0 < visibility < 2000:
        conditions.append(
            {
                "id": f"{point_id}-low_visibility",
                "type": "low_visibility",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"{visibility / 1000:.1f} km",
            }
        )

    if uv >= 8:
        conditions.append(
            {
                "id": f"{point_id}-high_uv",
                "type": "high_uv",
                "category": "weather",
                "lat": lat,
                "lon": lon,
                "reading": f"UV {round(uv)}",
            }
        )

    if temp <= 2 and 51 <= code <= 67:
        conditions.append(
            {
                "id": f"{point_id}-icing",
                "type": "icing",
                "category": "weather",
                "lat": lat,
                "lon": lon,
            }
        )

    if code >= 95:
        conditions.append(
            {
                "id": f"{point_id}-storm_warning",
                "type": "storm_warning",
                "category": "environmental",
                "lat": lat,
                "lon": lon,
            }
        )

    if code >= 63 and humidity > 80:
        conditions.append(
            {
                "id": f"{point_id}-flood_risk",
                "type": "flood_risk",
                "category": "environmental",
                "lat": lat,
                "lon": lon,
            }
        )

    if 0 < visibility < 3000 and wind > 8 and humidity < 40:
        conditions.append(
            {
                "id": f"{point_id}-dust",
                "type": "dust",
                "category": "weather",
                "lat": lat,
                "lon": lon,
            }
        )

    return conditions


async def fetch_open_meteo(lat: float, lon: float) -> dict[str, Any]:
    cache_key = f"openmeteo:{lat:.2f}:{lon:.2f}"
    cached = await space_weather_service._cache_get(cache_key)
    if cached:
        return cached

    url = f"{OPEN_METEO}&latitude={lat}&longitude={lon}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        current = resp.json().get("current", {})
        await space_weather_service._cache_set(cache_key, current, ttl=600)
        return current


async def fetch_map_conditions(
    points: list[dict[str, Any]], destination_code: str | None = None
) -> list[dict[str, Any]]:
    all_conditions: list[dict[str, Any]] = []

    for i, point in enumerate(points[:8]):
        lat = float(point["lat"])
        lon = float(point["lon"])
        point_id = str(point.get("id", f"pt-{i}"))
        try:
            data = await fetch_open_meteo(lat, lon)
            mapped = map_weather_to_conditions(data, lat, lon, point_id)
            for j, cond in enumerate(mapped):
                angle = (j * 137.5 * 3.14159) / 180
                radius = 0.04 + j * 0.015
                cond["lat"] = lat + math.cos(angle) * radius
                cond["lon"] = lon + math.sin(angle) * radius
            all_conditions.extend(mapped)
        except Exception:
            continue

    kp_data = await space_weather_service.fetch_kp_index()
    kp = int(kp_data.get("kp_index") or 0)
    if kp >= 5 and points:
        p = points[0]
        all_conditions.append(
            {
                "id": "solar-kp",
                "type": "solar",
                "category": "weather",
                "lat": float(p["lat"]) + 0.05,
                "lon": float(p["lon"]) + 0.05,
                "reading": f"Kp {kp}",
            }
        )

    if destination_code and destination_code.upper() == "JNPT" and points:
        p = points[-1]
        all_conditions.append(
            {
                "id": "op-port-jnpt",
                "type": "port_active",
                "category": "operational",
                "lat": float(p["lat"]),
                "lon": float(p["lon"]),
            }
        )

    return all_conditions
