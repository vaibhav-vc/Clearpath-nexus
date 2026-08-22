from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.schemas.schedule import TrainScheduleCreate
from app.services.scheduling import assess_schedule

IST = ZoneInfo("Asia/Kolkata")


def sched(
    *,
    code="X1",
    src="PUNE",
    dst="KYN",
    dep=(2026, 8, 22, 9, 0),
    arr=(2026, 8, 22, 11, 0),
    berth=None,
    status="PLANNED",
    ident="1",
):
    bw_start = bw_end = None
    if berth:
        bw_start = datetime(*berth[0], tzinfo=IST)
        bw_end = datetime(*berth[1], tzinfo=IST)
    return SimpleNamespace(
        id=ident,
        train_code=code,
        source_station_code=src,
        dest_station_code=dst,
        scheduled_departure=datetime(*dep, tzinfo=IST),
        scheduled_arrival=datetime(*arr, tzinfo=IST),
        berth_window_start=bw_start,
        berth_window_end=bw_end,
        schedule_status=status,
    )


def test_clear_schedule_is_ready_candidate():
    item = sched()
    status, reason = assess_schedule(item, [])
    assert status == "CLEAR"
    assert reason is None


def test_maintenance_conflict_is_blocked():
    item = sched(src="BSL", dst="JNPT", dep=(2026, 8, 22, 14, 0), arr=(2026, 8, 22, 20, 0))
    status, reason = assess_schedule(item, [])
    assert status == "BLOCKED"
    assert "maintenance" in reason.lower()


def test_berth_mismatch_is_warning():
    item = sched(
        src="PUNE",
        dst="JNPT",
        dep=(2026, 8, 22, 6, 0),
        arr=(2026, 8, 22, 9, 0),
        berth=((2026, 8, 22, 10, 0), (2026, 8, 22, 12, 0)),
    )
    status, reason = assess_schedule(item, [])
    assert status == "WARNING"
    assert "berth" in reason.lower()


def test_shared_destination_overlap_is_warning():
    item = sched(code="X1", dst="KYN", dep=(2026, 8, 22, 9, 0), arr=(2026, 8, 22, 11, 0), ident="1")
    other = sched(
        code="X2", dst="KYN", dep=(2026, 8, 22, 10, 0), arr=(2026, 8, 22, 12, 0), ident="2"
    )
    status, reason = assess_schedule(item, [other])
    assert status == "WARNING"
    assert "X2" in reason


def test_schedule_schema_rejects_backwards_time():
    try:
        TrainScheduleCreate(
            train_code="X1",
            train_name="Test",
            source_station_code="NGP",
            dest_station_code="JNPT",
            scheduled_departure=datetime(2026, 8, 22, 12, tzinfo=IST),
            scheduled_arrival=datetime(2026, 8, 22, 11, tzinfo=IST),
        )
    except ValueError as exc:
        assert "scheduled_arrival" in str(exc)
    else:
        raise AssertionError("Expected validation failure")
