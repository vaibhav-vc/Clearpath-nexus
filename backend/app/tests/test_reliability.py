from app.services.reliability import apply_threat_simulation, calculate_route_reliability


def test_reliability_formula():
    score = calculate_route_reliability(80, 90, 70, 60, clearance_failed=False)
    expected = int(__import__("math").ceil(0.4 * 80 + 0.3 * 90 + 0.15 * 70 + 0.15 * 60))
    assert score == expected


def test_clearance_override():
    score = calculate_route_reliability(100, 100, 100, 100, clearance_failed=True)
    assert score == 0


def test_threat_simulation():
    simulated, alerts = apply_threat_simulation(
        85, storm_severity=50, solar_kp_index=8, port_congestion=30
    )
    assert simulated < 85
    assert len(alerts) >= 2
