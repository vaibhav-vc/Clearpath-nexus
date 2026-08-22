import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limit import enforce_rate_limit


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def ttl(self, key: str) -> int:
        return 42

    async def aclose(self) -> None:
        return None


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "client": ("127.0.0.1", 1234),
            "headers": [],
        }
    )


@pytest.mark.asyncio
async def test_rate_limit_returns_retry_after_header() -> None:
    redis = FakeRedis()

    def factory(**_):
        return redis

    for _ in range(2):
        await enforce_rate_limit(make_request(), "operator@example.com", "login", 2, 60, factory)

    with pytest.raises(HTTPException) as error:
        await enforce_rate_limit(make_request(), "operator@example.com", "login", 2, 60, factory)

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "42"}
