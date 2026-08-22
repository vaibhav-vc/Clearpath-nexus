"""Guards the duplicated scoring logic.

reliability.py (backend) and DemoRouteEngine.kt (Android offline) implement
the same formula. These vectors are the shared contract: the Kotlin unit test
asserts the identical expected values, so drift in either fails CI.

If you change the formula, update BOTH sides and the vectors below.
"""

import json
import pathlib

import pytest

from app.services.reliability import calculate_route_reliability

# (weather, port, congestion, historical, clearance_failed, port_available) -> expected
VECTORS = [
    ((80, 90, 70, 60, False, True), 79),
    ((100, 100, 100, 100, False, True), 100),
    ((0, 0, 0, 0, False, True), 0),
    ((100, 100, 100, 100, True, True), 0),
    ((80, 0, 70, 60, False, False), 74),
    ((55, 40, 90, 20, False, True), 51),
    ((55, 40, 90, 20, False, False), 55),
]


@pytest.mark.parametrize("args,expected", VECTORS)
def test_reliability_vectors(args, expected):
    assert calculate_route_reliability(*args) == expected


def test_export_vectors_for_kotlin(tmp_path):
    """Emit the vectors so the Android test can consume the same contract."""
    payload = [{"args": list(a), "expected": e} for a, e in VECTORS]
    out = pathlib.Path(tmp_path) / "scoring_vectors.json"
    out.write_text(json.dumps(payload, indent=2))
    assert json.loads(out.read_text())[0]["expected"] == 79
