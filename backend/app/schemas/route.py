from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.services.congestion import CongestionSource
from app.services.port_sync import LoadingWindow, PortDataSource
from app.schemas.provenance import ProvenanceSummary


class OperatorLoadingWindow(BaseModel):
    """Vessel loading window entered by the operator from the manifest.

    Supplying this is the reliable path: there is no free public JNPT berth
    feed, so without it port alignment is excluded from the score.
    """

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def _check_order(self) -> "OperatorLoadingWindow":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class _HasPortWindow(BaseModel):
    """Mixin: shared operator-window plumbing for route requests."""

    loading_window: OperatorLoadingWindow | None = None

    def operator_loading_window(self) -> LoadingWindow | None:
        if self.loading_window is None:
            return None
        return LoadingWindow(start=self.loading_window.start_time, end=self.loading_window.end_time)


class CargoDimensions(BaseModel):
    height: float = Field(..., gt=0, description="Cargo height in meters")
    width: float = Field(..., gt=0, description="Cargo width in meters")
    weight: float = Field(..., gt=0, description="Cargo weight in tons")


class RouteEvaluateRequest(_HasPortWindow):
    cargo: CargoDimensions
    source_code: str = Field(..., min_length=2, max_length=10)
    dest_code: str = Field(..., min_length=2, max_length=10)
    port_id: str = "JNPT_MUMBAI"
    vessel_id: str = "MAERSK_X26"
    train_arrival_hours: float = Field(
        24.0, gt=0, description="Expected train arrival offset in hours"
    )


class TrainLocationInput(BaseModel):
    mode: str = Field(..., pattern="^(station|coordinates|live)$")
    station_code: str | None = None
    lat: float | None = None
    lon: float | None = None


class RouteSuggestRequest(_HasPortWindow):
    cargo: CargoDimensions
    destination_code: str = Field(..., min_length=2, max_length=10)
    location: TrainLocationInput
    port_id: str = "JNPT_MUMBAI"
    vessel_id: str = "MAERSK_X26"
    train_arrival_hours: float = Field(24.0, gt=0)


class TrackSegmentDetail(BaseModel):
    id: UUID
    label: str
    phase: str
    distance_km: float
    progress_pct: int | None = None
    max_height: float
    max_width: float
    max_weight: float
    congestion: float
    historical_delay_hours: float
    clearance_status: str
    advisory: str | None = None


class AlternateRoute(BaseModel):
    label: str
    reliability_score: int
    segment_ids: list[UUID]
    estimated_hours: float | None = None
    weather_score: float | None = None


class TrainPosition(BaseModel):
    lat: float
    lon: float
    mode: str
    snapped_track: str | None = None
    offset_km: float | None = None
    station_code: str | None = None


class ScoreBreakdown(BaseModel):
    weather: float
    port: float
    congestion: float
    historical: float
    # Where the port figure came from, and whether it counted at all.
    port_data_source: PortDataSource = PortDataSource.UNAVAILABLE
    port_counted: bool = False
    applied_weights: dict[str, float] = {}
    # How the congestion figure was reached: seeded baseline, or baseline
    # blended with live rail/AIS telemetry.
    congestion_source: CongestionSource = CongestionSource.STATIC_ONLY
    congestion_static: float | None = None
    congestion_live_rail: float | None = None
    port_congestion_pct: float | None = None


class SegmentPathPoint(BaseModel):
    lat: float
    lon: float


class SegmentPathResponse(BaseModel):
    id: UUID
    status: str
    coordinates: list[list[float]]
    phase: str | None = None
    label: str | None = None


class RouteEvaluateResponse(BaseModel):
    route_id: UUID
    status: str
    reliability_score: int
    blocking_segment_id: UUID | None = None
    estimated_hours: float | None = None
    score_breakdown: ScoreBreakdown | None = None
    segments: list[SegmentPathResponse] = []
    environmental_alerts: list[str] = []
    provenance_summary: ProvenanceSummary | None = None


class RouteSuggestResponse(RouteEvaluateResponse):
    train_position: TrainPosition
    remaining_km: float
    eta_hours: float | None = None
    track_details: list[TrackSegmentDetail] = []
    alternate_routes: list[AlternateRoute] = []
    next_station: str | None = None


class StationResponse(BaseModel):
    id: UUID
    name: str
    code: str
    lat: float
    lon: float

    model_config = {"from_attributes": True}


class ThreatSimulationRequest(BaseModel):
    storm_severity: float = Field(0.0, ge=0, le=100)
    solar_kp_index: int = Field(0, ge=0, le=9)
    port_congestion: float = Field(0.0, ge=0, le=100)


class ThreatSimulationResponse(BaseModel):
    original_score: int
    simulated_score: int
    degradation_pct: float
    alerts: list[str]


class RouteHistoryResponse(BaseModel):
    id: UUID
    source_station_code: str
    dest_station_code: str
    cargo_height_requested: float
    cargo_width_requested: float
    cargo_weight_requested: float
    status: str
    dispatch_status: str
    reliability_score: int
    estimated_hours: float | None = None
    dispatched_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RouteDispatchResponse(BaseModel):
    route_id: UUID
    dispatch_status: str
    dispatched_at: datetime
