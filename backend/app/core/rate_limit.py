from __future__ import annotations

import hashlib
import logging
from typing import Callable

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


def _identity(request: Request, subject: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    value = f"{client_ip}:{subject.strip().lower()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def enforce_rate_limit(
    request: Request,
    subject: str,
    action: str,
    limit: int,
    window_seconds: int,
    redis_factory: Callable[..., Redis] = Redis,
) -> None:
    key = f"nexus:rate:{action}:{_identity(request, subject)}"
    redis = redis_factory(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count > limit:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many {action} attempts. Try again later.",
                headers={"Retry-After": str(max(ttl, 1))},
            )
    except HTTPException:
        raise
    except Exception as exc:
        if settings.ENVIRONMENT.lower() in {"production", "staging"}:
            logger.error("Rate-limit store unavailable: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication protection temporarily unavailable",
                headers={"Retry-After": "30"},
            ) from exc
        logger.warning("Rate-limit store unavailable in development: %s", exc)
    finally:
        await redis.aclose()
