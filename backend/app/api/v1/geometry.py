from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.services.geometry_service import fetch_railway_geometry_from_overpass

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/track")
async def get_railway_track_geometry(
    min_lat: float = Query(..., ge=-90, le=90, description="Minimum latitude"),
    min_lon: float = Query(..., ge=-180, le=180, description="Minimum longitude"),
    max_lat: float = Query(..., ge=-90, le=90, description="Maximum latitude"),
    max_lon: float = Query(..., ge=-180, le=180, description="Maximum longitude"),
) -> dict:
    if max_lat <= min_lat or max_lon <= min_lon:
        raise HTTPException(
            status_code=422, detail="Bounding-box maximums must be greater than minimums"
        )
    tracks = await fetch_railway_geometry_from_overpass(min_lat, min_lon, max_lat, max_lon)
    return {"tracks": tracks, "count": len(tracks)}
