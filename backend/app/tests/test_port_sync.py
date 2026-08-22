"""Port sync must never silently invent a schedule."""

from datetime import datetime, timedelta, timezone

from app.services.port_sync import (
    LoadingWindow,
    PortDataSource,
    PortSchedule,
    compute_port_sync,
)
from app.services.reliability import calculate_route_reliability

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _window(start_h: float, end_h: float) -> LoadingWindow:
    return LoadingWindow(start=NOW + timedelta(hours=start_h), end=NOW + timedelta(hours=end_h))


def _schedule(source=PortDataSource.LIVE_FEED, window=None) -> PortSchedule:
    return PortSchedule(source=source, window=window or _window(12, 48))


def test_unavailable_is_not_a_zero_score():
    """The bug: an unreachable feed used to look like a terrible port score."""
    result = compute_port_sync(24.0, PortSchedule(source=PortDataSource.UNAVAILABLE))
    assert result.available is False
    assert result.aligned is False
    assert result.warning and "excluded" in result.warning.lower()


def test_unavailable_port_does_not_drag_the_score_down():
    with_port_missing = calculate_route_reliability(80, 0, 70, 60, port_available=False)
    as_if_port_were_terrible = calculate_route_reliability(80, 0, 70, 60, port_available=True)
    assert with_port_missing > as_if_port_were_terrible


def test_operator_window_is_scored_normally():
    result = compute_port_sync(24.0, _schedule(PortDataSource.OPERATOR_INPUT), now=NOW)
    assert result.available is True
    assert result.source is PortDataSource.OPERATOR_INPUT
    assert 0 < result.score <= 100
    assert result.evaluated_at == NOW
    assert result.train_arrival_hours == 24.0
    assert result.window == _schedule(PortDataSource.OPERATOR_INPUT).window


def test_arrival_inside_window_is_aligned():
    result = compute_port_sync(24.0, _schedule(window=_window(12, 48)), now=NOW)
    assert result.aligned is True
    assert result.warning is None
    assert result.score >= 60


def test_arrival_after_window_is_critical():
    result = compute_port_sync(72.0, _schedule(window=_window(12, 48)), now=NOW)
    assert result.score == 0.0
    assert result.aligned is False
    assert "misses vessel loading window" in result.warning


def test_early_arrival_warns_but_does_not_zero():
    result = compute_port_sync(1.0, _schedule(window=_window(12, 48)), now=NOW)
    assert result.aligned is False
    assert result.score >= 40.0
    assert "early" in result.warning
