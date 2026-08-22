from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.schemas.railways import IndianRailwaysNetworkResponse, LiveCorridorTrafficResponse
from app.services.indian_railways_service import fetch_indian_railways_live_forecast
from app.services.railradar import fetch_trains_between

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/indian-network-forecast", response_model=IndianRailwaysNetworkResponse)
async def get_indian_railways_network_forecast() -> IndianRailwaysNetworkResponse:
    return await fetch_indian_railways_live_forecast()


@router.get("/live-corridor-traffic", response_model=LiveCorridorTrafficResponse)
async def get_live_corridor_traffic(
    source_code: str = "NGP", dest_code: str = "JNPT"
) -> LiveCorridorTrafficResponse:
    """Optional live-data demo layer (RailRadar sandbox).

    Covers passenger/PRS trains only — this is a proof-of-concept live
    integration, not a freight-operations feed. Returns available=false
    with an explanatory message whenever RAILRADAR_API_KEY is unset or the
    provider fails; never fabricates traffic data.
    """
    result = await fetch_trains_between(source_code, dest_code)
    return LiveCorridorTrafficResponse(**result)
