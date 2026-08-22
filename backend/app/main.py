from contextlib import asynccontextmanager
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.observability import (
    configure_logging,
    metrics_registry,
    provider_status,
    request_duration_ms,
)

logger = logging.getLogger(__name__)

UUID_PATH_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?=/|$)"
)


def normalized_metrics_path(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str):
        return template
    return UUID_PATH_RE.sub("/{id}", request.url.path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Load an available model before accepting traffic so the first prediction
    # does not pay the deserialization/import cost. A missing or invalid model
    # remains a safe deterministic fallback and must not block API startup.
    if settings.ENABLE_ML_INFERENCE:
        from app.services.ml_prediction import delay_prediction_service

        delay_prediction_service.load()
        if delay_prediction_service.metadata is None:
            logger.warning("ML model unavailable; deterministic delay fallback is active")
    yield
    from app.core.database import engine
    from app.services.space_weather import space_weather_service

    await engine.dispose()
    await space_weather_service.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="6.0.0",
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)

app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def add_security_headers_and_request_log(request: Request, call_next):
    candidate_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        candidate_request_id
        if candidate_request_id
        and len(candidate_request_id) <= 64
        and candidate_request_id.isascii()
        else str(uuid4())
    )
    request.state.request_id = request_id
    started_at = perf_counter()
    status_code = 500
    try:
        response: Response = await call_next(request)
        status_code = response.status_code
    except Exception:
        duration_sec = perf_counter() - started_at
        metrics_registry.record_request(request.method, normalized_metrics_path(request), 500, duration_sec)
        logger.exception(
            "request_failed",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path},
        )
        raise

    duration_sec = perf_counter() - started_at
    metrics_registry.record_request(
        request.method, normalized_metrics_path(request), status_code, duration_sec
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/v1/auth") else "no-cache"
    )
    if settings.ENVIRONMENT.lower() in {"production", "staging"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": request_duration_ms(started_at),
        },
    )
    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    from sqlalchemy import text

    from app.core.database import AsyncSessionLocal
    from redis.asyncio import Redis

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=2,
        )
        await redis.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database or Redis dependency is unavailable",
        ) from exc
    await redis.aclose()
    return {"status": "ready", "service": settings.PROJECT_NAME}


@app.get("/status/providers")
async def provider_health() -> dict[str, object]:
    """Expose freshness state for operational provider monitoring."""
    return {"providers": provider_status.snapshot()}


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """Export Prometheus telemetry format."""
    return Response(
        content=metrics_registry.export_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
