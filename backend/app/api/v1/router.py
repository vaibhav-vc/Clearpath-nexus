from fastapi import APIRouter

from app.api.v1 import (
    compliance,
    geometry,
    live,
    live_ops,
    ml,
    multimodal,
    operations,
    planner,
    port,
    predictive,
    provenance,
    railways,
    weather,
)

api_router = APIRouter()
api_router.include_router(planner.router, prefix="/planner", tags=["planner"])
api_router.include_router(port.router, prefix="/port", tags=["port"])
api_router.include_router(weather.router, prefix="/weather", tags=["weather"])
api_router.include_router(geometry.router, prefix="/geometry", tags=["geometry"])
api_router.include_router(predictive.router, prefix="/predictive", tags=["predictive"])
api_router.include_router(railways.router, prefix="/railways", tags=["railways"])
api_router.include_router(live.router, prefix="/live", tags=["live"])
api_router.include_router(live_ops.router, prefix="/live", tags=["live-operations"])
api_router.include_router(ml.router, tags=["machine-learning"])
api_router.include_router(
    multimodal.router, prefix="/multimodal", tags=["multimodal-planning"]
)
api_router.include_router(
    operations.router, prefix="/operations", tags=["integrated-operations"]
)
api_router.include_router(provenance.router, prefix="/provenance", tags=["provenance"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
