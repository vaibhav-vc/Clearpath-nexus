"""Route Reliability Index (RRI).

This module is the single source of truth for scoring. The Android offline
engine (DemoRouteEngine.kt) mirrors it; tests/test_scoring_parity.py asserts
the two stay in agreement.
"""

import math

from app.core.config import settings


def calculate_route_reliability(
    weather_score: float,
    port_sync_score: float,
    congestion_score: float,
    historical_delay_score: float,
    clearance_failed: bool = False,
    port_available: bool = True,
) -> int:
    """NEXUS-004: Multi-factor route reliability scoring matrix.

    When port data is unavailable we drop the port term and renormalise the
    remaining weights, rather than feeding in a placeholder. A missing input
    should widen uncertainty, not silently pin 30% of the score to a constant.

    With all four factors present the weights sum to 1.0, so this reduces
    exactly to the original formula.
    """
    if clearance_failed:
        return 0

    factors: list[tuple[float, float]] = [
        (settings.WEIGHT_WEATHER_RISK, weather_score),
        (settings.WEIGHT_CORRIDOR_CONGESTION, congestion_score),
        (settings.WEIGHT_HISTORICAL_DELAY, historical_delay_score),
    ]
    if port_available:
        factors.append((settings.WEIGHT_PORT_ALIGNMENT, port_sync_score))

    total_weight = sum(weight for weight, _ in factors)
    if total_weight <= 0:
        return 0

    composite = sum(weight * score for weight, score in factors) / total_weight
    return int(math.ceil(composite))


def effective_weights(port_available: bool = True) -> dict[str, float]:
    """The weights actually applied, after renormalisation. For UI display."""
    raw = {
        "weather": settings.WEIGHT_WEATHER_RISK,
        "congestion": settings.WEIGHT_CORRIDOR_CONGESTION,
        "historical": settings.WEIGHT_HISTORICAL_DELAY,
    }
    if port_available:
        raw["port"] = settings.WEIGHT_PORT_ALIGNMENT

    total = sum(raw.values())
    return {key: round(value / total, 4) for key, value in raw.items()}


def apply_threat_simulation(
    base_score: int,
    storm_severity: float,
    solar_kp_index: int,
    port_congestion: float,
) -> tuple[int, list[str]]:
    """Threat Simulation Center - degrade score under artificial stress."""
    alerts: list[str] = []
    penalty = 0.0

    if storm_severity > 0:
        penalty += storm_severity * 0.35
        alerts.append(f"Heavy storm simulation active (severity {storm_severity:.0f}%)")

    if solar_kp_index >= 7:
        penalty += (solar_kp_index - 6) * 12
        alerts.append(f"CRITICAL: Kp-index {solar_kp_index} - geomagnetic telemetry risk")

    if port_congestion > 0:
        penalty += port_congestion * 0.25
        alerts.append(f"Port gridlock simulation (congestion {port_congestion:.0f}%)")

    simulated = max(0, int(base_score - penalty))
    return simulated, alerts
