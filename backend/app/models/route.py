import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    coordinates = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=False, index=True
    )

    outgoing_segments: Mapped[list["LineSegment"]] = relationship(
        "LineSegment",
        foreign_keys="LineSegment.source_station_id",
        back_populates="source_station",
    )
    incoming_segments: Mapped[list["LineSegment"]] = relationship(
        "LineSegment",
        foreign_keys="LineSegment.dest_station_id",
        back_populates="dest_station",
    )


class LineSegment(Base):
    __tablename__ = "line_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stations.id"), nullable=False
    )
    dest_station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stations.id"), nullable=False
    )
    max_height_clearance: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    max_width_clearance: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    max_weight_capacity: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    congestion_factor: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.0)
    historical_delay_hours: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=0.0
    )
    geom_path = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326), nullable=False, index=True
    )

    source_station: Mapped["Station"] = relationship(
        "Station", foreign_keys=[source_station_id], back_populates="outgoing_segments"
    )
    dest_station: Mapped["Station"] = relationship(
        "Station", foreign_keys=[dest_station_id], back_populates="incoming_segments"
    )


class PortBerth(Base):
    __tablename__ = "port_berths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    port_name: Mapped[str] = mapped_column(String(100), nullable=False)
    berth_identifier: Mapped[str] = mapped_column(String(20), nullable=False)
    vessel_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GeneratedRoute(Base):
    __tablename__ = "generated_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cargo_height_requested: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    cargo_width_requested: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    cargo_weight_requested: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    source_station_code: Mapped[str] = mapped_column(String(10), nullable=False)
    dest_station_code: Mapped[str] = mapped_column(String(10), nullable=False)
    # Clearance state. Keep separate from dispatch lifecycle.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    dispatch_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", index=True
    )
    reliability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    blocking_segment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainSchedule(Base):
    __tablename__ = "train_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    generated_route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_routes.id"), nullable=True, index=True
    )
    train_code: Mapped[str] = mapped_column(String(20), nullable=False)
    train_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_station_code: Mapped[str] = mapped_column(String(10), nullable=False)
    dest_station_code: Mapped[str] = mapped_column(String(10), nullable=False)
    scheduled_departure: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    berth_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    berth_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    schedule_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PLANNED", index=True
    )
    conflict_status: Mapped[str] = mapped_column(String(20), nullable=False, default="CLEAR")
    conflict_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
