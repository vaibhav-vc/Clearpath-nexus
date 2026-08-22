from pydantic import BaseModel, Field


class MapConditionPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    id: str | None = None


class MapConditionsRequest(BaseModel):
    points: list[MapConditionPoint] = Field(..., min_length=1)
    destination_code: str | None = Field(default=None, max_length=10, pattern=r"^[A-Za-z0-9_-]+$")


class MapConditionResponse(BaseModel):
    id: str
    type: str
    category: str
    lat: float
    lon: float
    reading: str | None = None
    detail: str | None = None


class MapConditionsResponse(BaseModel):
    conditions: list[MapConditionResponse]
    source: str = "open-meteo"


class RouteWeatherPointRequest(MapConditionPoint):
    id: str = Field(..., min_length=1, max_length=100)


class RouteWeatherPointsRequest(BaseModel):
    points: list[RouteWeatherPointRequest] = Field(..., min_length=1, max_length=8)


class RouteWeatherPointResponse(BaseModel):
    id: str
    lat: float
    lon: float
    available: bool
    temperature_2m: float | None = None
    apparent_temperature: float | None = None
    relative_humidity_2m: float | None = None
    weather_code: int | None = None
    wind_speed_10m: float | None = None
    wind_direction_10m: float | None = None
    visibility: float | None = None
    uv_index: float | None = None
    precipitation: float | None = None
    message: str | None = None


class RouteWeatherPointsResponse(BaseModel):
    points: list[RouteWeatherPointResponse]
    source: str = "open-meteo"
