from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

IST = ZoneInfo("Asia/Kolkata")


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _crosses_maintenance_corridor(source: str, dest: str) -> bool:
    westbound_sources = {"NGP", "BSL", "MMR"}
    westbound_destinations = {"KYN", "JNPT"}
    return source.upper() in westbound_sources and dest.upper() in westbound_destinations


def assess_schedule(
    schedule: Any,
    others: list[Any],
) -> tuple[str, str | None]:
    """Small deterministic scheduler guardrail for the demo/MVP.

    It intentionally does not replace the route engine. It checks only three
    operational concerns: a seeded maintenance block, coarse corridor slot
    overlap, and an operator-supplied berth window.
    """
    dep = schedule.scheduled_departure
    arr = schedule.scheduled_arrival

    # Daily demo maintenance block on the MMR -> KYN corridor, 14:00-16:00 IST.
    dep_ist = dep.astimezone(IST)
    maintenance_start = datetime.combine(dep_ist.date(), time(14, 0), tzinfo=IST)
    maintenance_end = datetime.combine(dep_ist.date(), time(16, 0), tzinfo=IST)
    if _crosses_maintenance_corridor(schedule.source_station_code, schedule.dest_station_code):
        if _overlaps(dep, arr, maintenance_start, maintenance_end):
            return (
                "BLOCKED",
                "MMR→KYN maintenance block overlaps this movement (14:00–16:00 IST). Recommended departure: 16:15 IST.",
            )

    # Operator berth window: arrival outside the supplied window is a warning,
    # not a fabricated hard block.
    if schedule.berth_window_start and schedule.berth_window_end:
        if not (schedule.berth_window_start <= arr <= schedule.berth_window_end):
            return (
                "WARNING",
                "Arrival falls outside the operator berth window. Shift departure to reduce terminal waiting.",
            )

    # Coarse shared-corridor proxy for MVP: same destination and overlapping
    # movement windows. A real signalling/section-occupation engine can replace
    # this later without changing the API contract.
    for other in others:
        if other.id == schedule.id or other.schedule_status == "CANCELLED":
            continue
        same_constrained_end = other.dest_station_code == schedule.dest_station_code
        if same_constrained_end and _overlaps(
            dep, arr, other.scheduled_departure, other.scheduled_arrival
        ):
            return (
                "WARNING",
                f"Train-slot overlap with {other.train_code} on the approach to {schedule.dest_station_code}. Recommended shift: +30 min.",
            )

    return "CLEAR", None


async def ensure_demo_schedules(db: AsyncSession, user_id: str) -> None:
    # Delayed import keeps the deterministic conflict checker unit-testable
    # without requiring PostGIS/GeoAlchemy to be installed.
    from app.models.route import TrainSchedule

    existing = await db.execute(
        select(TrainSchedule.id)
        .where(
            TrainSchedule.user_id == user_id,
            TrainSchedule.is_demo.is_(True),
        )
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    now_ist = datetime.now(IST)
    day = now_ist.date() if now_ist.time() < time(22, 0) else (now_ist + timedelta(days=1)).date()

    def at(hour: int, minute: int = 0, day_offset: int = 0) -> datetime:
        return datetime.combine(day + timedelta(days=day_offset), time(hour, minute), tzinfo=IST)

    demos = [
        TrainSchedule(
            user_id=user_id,
            train_code="CPN-101",
            train_name="Western Freight",
            source_station_code="NGP",
            dest_station_code="JNPT",
            scheduled_departure=at(6, 30),
            scheduled_arrival=at(12, 30),
            schedule_status="READY",
            conflict_status="CLEAR",
            conflict_reason=None,
            is_demo=True,
        ),
        TrainSchedule(
            user_id=user_id,
            train_code="CPN-202",
            train_name="Deccan Cargo",
            source_station_code="NGP",
            dest_station_code="KYN",
            scheduled_departure=at(9, 15),
            scheduled_arrival=at(15, 0),
            schedule_status="PLANNED",
            conflict_status="WARNING",
            conflict_reason="Shared KYN approach slot is busy. Recommended departure shift: +30 min.",
            is_demo=True,
        ),
        TrainSchedule(
            user_id=user_id,
            train_code="CPN-303",
            train_name="SteelLink",
            source_station_code="BSL",
            dest_station_code="JNPT",
            scheduled_departure=at(14, 0),
            scheduled_arrival=at(21, 30),
            schedule_status="PLANNED",
            conflict_status="BLOCKED",
            conflict_reason="MMR→KYN maintenance block 14:00–16:00 IST. Recommended departure: 16:15 IST.",
            is_demo=True,
        ),
        TrainSchedule(
            user_id=user_id,
            train_code="CPN-404",
            train_name="Port Connector",
            source_station_code="MMR",
            dest_station_code="JNPT",
            scheduled_departure=at(20, 30),
            scheduled_arrival=at(2, 30, 1),
            berth_window_start=at(23, 0),
            berth_window_end=at(1, 30, 1),
            schedule_status="PLANNED",
            conflict_status="WARNING",
            conflict_reason="Arrival is after the operator berth window. Recommended departure shift: -60 min.",
            is_demo=True,
        ),
    ]
    db.add_all(demos)
    await db.commit()
