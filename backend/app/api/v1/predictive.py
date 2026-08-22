from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.schemas.predictive import (
    DelayPredictionRequest,
    DelayPredictionResponse,
    DustStormRiskResponse,
)
from app.services.dust_storm_service import analyze_dust_storm_hazard
from app.services.predictive_delay import calculate_predictive_delay

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/delay", response_model=DelayPredictionResponse)
async def predict_route_delay(payload: DelayPredictionRequest) -> DelayPredictionResponse:
    return calculate_predictive_delay(
        source_code=payload.source_code,
        dest_code=payload.dest_code,
        cargo_weight=payload.cargo_weight,
        train_arrival_hours=payload.train_arrival_hours,
    )


@router.get("/dust-risk", response_model=DustStormRiskResponse)
async def get_dust_storm_risk(
    lat: float = Query(21.1458, ge=-90, le=90, description="Latitude"),
    lon: float = Query(79.0882, ge=-180, le=180, description="Longitude"),
    location: str = Query("Nagpur Corridor", min_length=1, max_length=100, description="Node name"),
) -> DustStormRiskResponse:
    return analyze_dust_storm_hazard(lat, lon, location)
