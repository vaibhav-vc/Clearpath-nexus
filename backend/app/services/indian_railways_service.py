from __future__ import annotations

import logging
from datetime import datetime, timezone
import httpx

from app.schemas.railways import IndianRailwaysNetworkResponse, RailwayZoneStatus, StationForecast
from app.services.space_weather import space_weather_service

logger = logging.getLogger(__name__)

INDIAN_RAILWAY_STATIONS = [
    {"code": "NGP", "name": "Nagpur Junction", "zone": "CR", "lat": 21.1458, "lon": 79.0882},
    {"code": "BSL", "name": "Bhusaval Junction", "zone": "CR", "lat": 21.0455, "lon": 75.7849},
    {"code": "MMR", "name": "Manmad Junction", "zone": "CR", "lat": 20.2500, "lon": 74.4333},
    {"code": "KYN", "name": "Kalyan Junction", "zone": "CR", "lat": 19.2433, "lon": 73.1305},
    {"code": "JNPT", "name": "Mumbai Port (JNPT)", "zone": "CR", "lat": 18.9497, "lon": 72.9512},
    {"code": "PUNE", "name": "Pune Junction", "zone": "CR", "lat": 18.5285, "lon": 73.8740},
    {"code": "NDLS", "name": "New Delhi", "zone": "NR", "lat": 28.6139, "lon": 77.2090},
    {"code": "HWH", "name": "Howrah Junction", "zone": "ER", "lat": 22.5851, "lon": 88.3412},
    {"code": "MAS", "name": "Chennai Central", "zone": "SR", "lat": 13.0827, "lon": 80.2707},
    {"code": "SBC", "name": "KSR Bengaluru", "zone": "SWR", "lat": 12.9776, "lon": 77.5713},
]


async def fetch_indian_railways_live_forecast() -> IndianRailwaysNetworkResponse:
    forecasts: list[StationForecast] = []
    alerts: list[str] = []

    for st in INDIAN_RAILWAY_STATIONS:
        cache_key = f"ir_forecast:{st['code']}"
        cached = await space_weather_service._cache_get(cache_key)

        if cached:
            forecasts.append(StationForecast(**cached))
            continue

        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={st['lat']}&longitude={st['lon']}"
            "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,visibility,precipitation"
            "&timezone=Asia%2FKolkata"
        )
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                current = resp.json().get("current", {})

                required = {
                    "temperature_2m",
                    "wind_speed_10m",
                    "visibility",
                    "precipitation",
                    "weather_code",
                }
                if not required.issubset(current):
                    raise ValueError("Open-Meteo response is missing current forecast fields")

                temp = float(current["temperature_2m"])
                wind = float(current["wind_speed_10m"])
                vis_m = float(current["visibility"])
                vis_km = round(vis_m / 1000.0, 1)
                precip = float(current["precipitation"])
                # Calculate risk score
                risk = 10.0
                advisory = None

                if precip > 5.0:
                    risk += 35.0
                    advisory = "Heavy monsoon rainfall — speed reduction advised"
                elif wind > 25.0:
                    risk += 25.0
                    advisory = "Crosswind advisory on high bridges"
                elif vis_km < 3.0:
                    risk += 30.0
                    advisory = "Low visibility — fog/dust alert"

                risk = min(100.0, max(5.0, risk))

                fc = StationForecast(
                    station_code=st["code"],
                    station_name=st["name"],
                    zone=st["zone"],
                    lat=st["lat"],
                    lon=st["lon"],
                    current_temp_c=round(temp, 1),
                    wind_speed_kmh=round(wind, 1),
                    visibility_km=vis_km,
                    precipitation_mm=round(precip, 1),
                    condition_label="Rainy" if precip > 2.0 else "Clear",
                    risk_score=round(risk, 1),
                    delay_advisory=advisory,
                )
                forecasts.append(fc)
                await space_weather_service._cache_set(cache_key, fc.model_dump(), ttl=600)

                if advisory:
                    alerts.append(f"{st['code']}: {advisory}")

        except Exception as exc:
            logger.warning("Failed to fetch forecast for %s: %s", st["code"], exc)
            forecasts.append(
                StationForecast(
                    station_code=st["code"],
                    station_name=st["name"],
                    zone=st["zone"],
                    lat=st["lat"],
                    lon=st["lon"],
                    condition_label="UNAVAILABLE",
                    delay_advisory="Weather provider unavailable; do not use this record for dispatch decisions.",
                )
            )

    zones = [
        RailwayZoneStatus(
            zone_code="CR",
            zone_name="Central Railway Zone",
            weather_hazard="UNAVAILABLE",
            status="DATA_UNAVAILABLE",
        ),
        RailwayZoneStatus(
            zone_code="WR",
            zone_name="Western Railway Zone",
            weather_hazard="UNAVAILABLE",
            status="DATA_UNAVAILABLE",
        ),
        RailwayZoneStatus(
            zone_code="NR",
            zone_name="Northern Railway Zone",
            weather_hazard="UNAVAILABLE",
            status="DATA_UNAVAILABLE",
        ),
    ]

    return IndianRailwaysNetworkResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        overall_health_score=None,
        active_zones=zones,
        station_forecasts=forecasts,
        network_alerts=alerts,
    )
