"""Supabase JWT verification.

Auth is owned by Supabase; this module only *verifies* the token Supabase
issued. We never mint, refresh, or store credentials here.

Two verification paths, picked automatically:

  1. Asymmetric (preferred) - fetch the project's public keys from JWKS and
     verify RS256/ES256. No shared secret lives on the server.
  2. Symmetric (legacy) - HS256 using SUPABASE_JWT_SECRET, for older projects
     that have not migrated to signing keys.

Set SUPABASE_URL and the rest is derived.
"""

from __future__ import annotations

import logging
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Legacy seed/test helper; interactive authentication remains Supabase-owned."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Hash bootstrap data retained for backwards-compatible migrations/seeding."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Compatibility helpers for old, unmounted cookie-auth migrations and tests.
# Active API authentication is always performed by get_current_user below.
_LEGACY_ALGORITHM = "HS256"


def _create_legacy_token(
    subject: str | Any,
    token_type: str,
    expires_delta: timedelta,
    session_id: str | None = None,
    role: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "iat": now,
        "exp": now + expires_delta,
        "sub": str(subject),
        "type": token_type,
    }
    if session_id:
        claims["sid"] = str(session_id)
    if role:
        claims["role"] = role
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=_LEGACY_ALGORITHM)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    session_id: str | None = None,
    role: str | None = None,
) -> str:
    return _create_legacy_token(
        subject,
        "access",
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        session_id=session_id,
        role=role,
    )


def create_refresh_token(
    subject: str | Any,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    return _create_legacy_token(
        subject,
        "refresh",
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        session_id=session_id,
    )


def decode_access_token(token: str, expected_type: str = "access") -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_LEGACY_ALGORITHM])
        if payload.get("type", "access") != expected_type or not payload.get("sub"):
            return None
        return payload
    except jwt.InvalidTokenError:
        return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# auto_error=False so we can raise our own 401 with a useful message.
_bearer = HTTPBearer(auto_error=False)

_ASYMMETRIC_ALGS = ("RS256", "ES256")
_SYMMETRIC_ALGS = ("HS256",)

# PyJWKClient keeps its own TTL cache; we just avoid rebuilding the client.
_jwk_client: PyJWKClient | None = None
_jwk_client_failed_at: float = 0.0
_JWK_RETRY_SECONDS = 30.0


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, as asserted by Supabase."""

    id: str
    email: str | None
    role: str
    claims: dict[str, Any]

    @property
    def is_anonymous(self) -> bool:
        return self.role == "anon"


def _jwks_url() -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _get_jwk_client() -> PyJWKClient | None:
    """Lazily build the JWKS client. Returns None if the project has no JWKS."""
    global _jwk_client, _jwk_client_failed_at

    if _jwk_client is not None:
        return _jwk_client
    if not settings.SUPABASE_URL:
        return None
    # Back off briefly after a failure so every request isn't a network round trip.
    if time.monotonic() - _jwk_client_failed_at < _JWK_RETRY_SECONDS:
        return None

    try:
        client = PyJWKClient(_jwks_url(), cache_keys=True, lifespan=600)
        # Force one fetch so a misconfigured URL fails here, not mid-request.
        client.fetch_data()
        _jwk_client = client
        return _jwk_client
    except Exception as exc:
        _jwk_client_failed_at = time.monotonic()
        logger.warning(
            "JWKS unavailable at %s (%s); falling back to symmetric verification",
            _jwks_url(),
            exc,
        )
        return None


def _decode(token: str) -> dict[str, Any]:
    """Verify signature, expiry, and audience. Raises jwt exceptions on failure."""
    common: dict[str, Any] = {
        "audience": settings.SUPABASE_JWT_AUDIENCE,
        "options": {"require": ["exp", "sub"]},
    }

    client = _get_jwk_client()
    if client is not None:
        signing_key = client.get_signing_key_from_jwt(token).key
        return jwt.decode(token, signing_key, algorithms=list(_ASYMMETRIC_ALGS), **common)

    if settings.SUPABASE_JWT_SECRET:
        return jwt.decode(
            token, settings.SUPABASE_JWT_SECRET, algorithms=list(_SYMMETRIC_ALGS), **common
        )

    raise RuntimeError(
        "No verification material: set SUPABASE_URL (for JWKS) or SUPABASE_JWT_SECRET."
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """FastAPI dependency. Rejects anything that isn't a valid Supabase user token."""
    if settings.AUTH_DISABLED:
        # Explicit local-dev escape hatch, guarded so it cannot trip in production.
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DISABLED must not be set in production")
        logger.warning("AUTH_DISABLED - returning synthetic dev user")
        return CurrentUser(
            id="00000000-0000-0000-0000-000000000000",
            email="dev@local",
            role="authenticated",
            claims={},
        )

    if creds is None or not creds.credentials:
        raise _unauthorized("Missing bearer token")

    try:
        claims = _decode(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired")
    except jwt.InvalidAudienceError:
        raise _unauthorized("Token audience mismatch")
    except jwt.InvalidTokenError as exc:
        logger.info("Rejected token: %s", exc)
        raise _unauthorized("Invalid token")
    except RuntimeError as exc:
        # Server misconfiguration - do not leak it to the caller as a 401.
        logger.error("Auth misconfigured: %s", exc)
        raise HTTPException(status_code=500, detail="Authentication is not configured")

    subject = claims.get("sub")
    if not subject:
        raise _unauthorized("Token has no subject")

    user = CurrentUser(
        id=subject,
        email=claims.get("email"),
        role=claims.get("role", "authenticated"),
        claims=claims,
    )

    if user.is_anonymous:
        raise _unauthorized("Anonymous tokens cannot access this resource")

    return user


async def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser | None:
    """For endpoints that personalise when signed in but still work when not."""
    if creds is None:
        return None
    try:
        return await get_current_user(creds)
    except HTTPException:
        return None
