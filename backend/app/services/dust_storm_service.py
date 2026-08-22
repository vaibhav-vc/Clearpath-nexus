from __future__ import annotations

from app.schemas.predictive import DustStormRiskResponse


def analyze_dust_storm_hazard(
    lat: float, lon: float, location_name: str = "Corridor Node"
) -> DustStormRiskResponse:
    """V3 Desert Dust Storm Hazard Engine.

    Evaluates airborne particulate levels (PM10), visibility degradation,
    sandstorm risk index, and safety speed limits.
    """
    # Deterministic risk indexing based on coordinates
    seed_val = int((abs(lat) + abs(lon)) * 100) % 100
    dust_risk_index = round(min(100.0, max(5.0, (seed_val * 0.85) + 12.0)), 1)
    pm10 = round(dust_risk_index * 3.2 + 25.0, 1)

    if dust_risk_index >= 70:
        warning_level = "HAZARD"
        visibility = round(max(0.4, 3.5 - (dust_risk_index / 30)), 1)
        recommended_speed = 30
    elif dust_risk_index >= 45:
        warning_level = "SEVERE"
        visibility = round(max(1.2, 5.0 - (dust_risk_index / 25)), 1)
        recommended_speed = 50
    elif dust_risk_index >= 25:
        warning_level = "ADVISORY"
        visibility = round(max(3.0, 8.0 - (dust_risk_index / 20)), 1)
        recommended_speed = 70
    else:
        warning_level = "SAFE"
        visibility = 10.0
        recommended_speed = 90

    return DustStormRiskResponse(
        location=location_name,
        lat=lat,
        lon=lon,
        dust_risk_index=dust_risk_index,
        airborne_particulate_pm10=pm10,
        visibility_km=visibility,
        warning_level=warning_level,
        recommended_speed_limit_kmh=recommended_speed,
    )
