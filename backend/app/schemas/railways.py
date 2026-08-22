from pydantic import BaseModel


class StationForecast(BaseModel):
    station_code: str
    station_name: str
    zone: str
    lat: float
    lon: float
    current_temp_c: float | None = None
    wind_speed_kmh: float | None = None
    visibility_km: float | None = None
    precipitation_mm: float | None = None
    condition_label: str
    risk_score: float | None = None  # 0 (Low Risk) to 100 (High Risk)
    delay_advisory: str | None = None


class RailwayZoneStatus(BaseModel):
    zone_code: str  # e.g., CR (Central Railway), WR (Western Railway), NR (Northern Railway)
    zone_name: str
    active_trains: int | None = None
    health_score: float | None = None
    weather_hazard: str
    status: str  # OPERATIONAL, CAUTION, DEGRADED


class IndianRailwaysNetworkResponse(BaseModel):
    timestamp: str
    overall_health_score: float | None = None
    active_zones: list[RailwayZoneStatus]
    station_forecasts: list[StationForecast]
    network_alerts: list[str]


class LiveCorridorTrain(BaseModel):
    train_number: str
    train_name: str
    status: str
    delay_minutes: float | None = None


class LiveCorridorTrafficResponse(BaseModel):
    available: bool
    provider: str
    source_code: str | None = None
    dest_code: str | None = None
    trains: list[LiveCorridorTrain] = []
    alerts: list[str] = []
    message: str | None = None
