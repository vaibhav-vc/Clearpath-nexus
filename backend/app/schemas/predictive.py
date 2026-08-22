from pydantic import BaseModel, Field


class DelayPredictionRequest(BaseModel):
    source_code: str = Field(..., min_length=2, max_length=10, pattern=r"^[A-Za-z0-9_-]+$")
    dest_code: str = Field(..., min_length=2, max_length=10, pattern=r"^[A-Za-z0-9_-]+$")
    cargo_weight: float = Field(120.0, gt=0)
    train_arrival_hours: float = Field(24.0, gt=0)


class DelayPredictionResponse(BaseModel):
    predicted_delay_minutes: int
    confidence_pct: float
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    primary_bottleneck_segment: str | None = None
    weather_impact_pct: float
    congestion_impact_pct: float
    optimal_dispatch_window: str


class DustStormRiskResponse(BaseModel):
    location: str
    lat: float
    lon: float
    dust_risk_index: float  # 0 to 100
    airborne_particulate_pm10: float
    visibility_km: float
    warning_level: str  # SAFE, ADVISORY, SEVERE, HAZARD
    recommended_speed_limit_kmh: int
