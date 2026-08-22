from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TrainScheduleCreate(BaseModel):
    generated_route_id: UUID | None = None
    train_code: str = Field(..., min_length=2, max_length=20)
    train_name: str = Field(..., min_length=2, max_length=100)
    source_station_code: str = Field(..., min_length=2, max_length=10)
    dest_station_code: str = Field(..., min_length=2, max_length=10)
    scheduled_departure: datetime
    scheduled_arrival: datetime
    berth_window_start: datetime | None = None
    berth_window_end: datetime | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "TrainScheduleCreate":
        if self.scheduled_arrival <= self.scheduled_departure:
            raise ValueError("scheduled_arrival must be after scheduled_departure")
        if (self.berth_window_start is None) != (self.berth_window_end is None):
            raise ValueError("berth_window_start and berth_window_end must be supplied together")
        if self.berth_window_start and self.berth_window_end <= self.berth_window_start:
            raise ValueError("berth_window_end must be after berth_window_start")
        return self


class TrainScheduleUpdate(BaseModel):
    scheduled_departure: datetime | None = None
    scheduled_arrival: datetime | None = None
    berth_window_start: datetime | None = None
    berth_window_end: datetime | None = None
    schedule_status: str | None = Field(None, pattern="^(PLANNED|READY|CANCELLED)$")


class TrainScheduleResponse(BaseModel):
    id: UUID
    generated_route_id: UUID | None
    train_code: str
    train_name: str
    source_station_code: str
    dest_station_code: str
    scheduled_departure: datetime
    scheduled_arrival: datetime
    berth_window_start: datetime | None
    berth_window_end: datetime | None
    schedule_status: str
    conflict_status: str
    conflict_reason: str | None
    is_demo: bool
    dispatched_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
