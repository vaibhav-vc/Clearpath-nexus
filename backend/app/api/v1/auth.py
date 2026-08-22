import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.core.rate_limit import enforce_rate_limit
from app.models.user import AuthSession, User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    WebSessionResponse,
    RefreshTokenRequest,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# A fixed bcrypt hash ensures unknown-account attempts incur equivalent password work.
DUMMY_PASSWORD_HASH = "$2b$12$GEYFmz8UmlIiPS0lQO7S8Obuto5fpm2ED93t6bUJ8BiQItH0Qdyui"


def _set_web_session(response: Response, token: str, refresh_token: str | None = None) -> None:
    secure = settings.AUTH_COOKIE_SECURE or settings.ENVIRONMENT.lower() in {
        "production",
        "staging",
    }
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN or None,
        max_age=60 * 60 * 24,
        path="/",
    )
    if refresh_token:
        response.set_cookie(
            key=settings.AUTH_REFRESH_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite=settings.AUTH_COOKIE_SAMESITE,
            domain=settings.AUTH_COOKIE_DOMAIN or None,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/api/v1/auth",
        )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        httponly=False,
        secure=secure,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN or None,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def _require_csrf(request: Request) -> None:
    # Bearer-token clients are not exposed to browser cookie CSRF.
    if request.headers.get("authorization", "").lower().startswith("bearer "):
        return
    if request.cookies.get(settings.AUTH_COOKIE_NAME):
        cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
        header_token = request.headers.get("X-CSRF-Token")
        if (
            not cookie_token
            or not header_token
            or not secrets.compare_digest(cookie_token, header_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed"
            )


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = token or request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError):
        return None
    session_id = payload.get("sid")
    if session_id:
        try:
            session_uuid = UUID(str(session_id))
        except (TypeError, ValueError):
            return None
        session = await db.scalar(
            select(AuthSession).where(
                AuthSession.id == session_uuid,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(timezone.utc),
            )
        )
        if session is None:
            return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def require_current_user(
    request: Request,
    current_user: User | None = Depends(get_current_user),
) -> User:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        _require_csrf(request)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return current_user


async def require_operator(
    current_user: User = Depends(require_current_user),
) -> User:
    """Allow only operational roles on the protected API surface."""
    if current_user.role not in {"operator", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return current_user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not settings.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled; request an operator invitation",
        )
    await enforce_rate_limit(
        request,
        payload.email,
        "registration",
        settings.REGISTRATION_RATE_LIMIT,
        settings.REGISTRATION_RATE_WINDOW_SECONDS,
    )
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already registered",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role="operator",
    )
    db.add(user)
    try:
        await db.flush()
        return await _issue_token_pair(user, db)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email address already registered"
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: Request,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await enforce_rate_limit(
        request,
        payload.email,
        "login",
        settings.LOGIN_RATE_LIMIT,
        settings.LOGIN_RATE_WINDOW_SECONDS,
    )
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(payload.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return await _issue_token_pair(user, db)


async def _issue_token_pair(user: User, db: AsyncSession) -> TokenResponse:
    session = AuthSession(
        id=uuid4(),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc),
    )

    session.expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    refresh_token = create_refresh_token(str(user.id), str(session.id))
    session.refresh_token_hash = hash_token(refresh_token)
    access_token = create_access_token(str(user.id), session_id=str(session.id), role=user.role)
    db.add(session)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


async def _revoke_session(request: Request, db: AsyncSession) -> None:
    raw_token = request.headers.get("authorization", "")
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()
    else:
        raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME, "")
    payload = decode_access_token(raw_token) if raw_token else None
    if not payload or not payload.get("sid"):
        return
    try:
        session = await db.get(AuthSession, UUID(str(payload["sid"])))
    except (TypeError, ValueError):
        return
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        await db.commit()


@router.post(
    "/web/register", response_model=WebSessionResponse, status_code=status.HTTP_201_CREATED
)
async def register_web_user(
    response: Response,
    request: Request,
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> WebSessionResponse:
    token_response = await register_user(request, payload, db)
    _set_web_session(response, token_response.access_token, token_response.refresh_token)
    return WebSessionResponse(user=token_response.user)


@router.post("/web/login", response_model=WebSessionResponse)
async def login_web_user(
    response: Response,
    request: Request,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> WebSessionResponse:
    token_response = await login_user(request, payload, db)
    _set_web_session(response, token_response.access_token, token_response.refresh_token)
    return WebSessionResponse(user=token_response.user)


@router.post("/web/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_web_user(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> Response:
    _require_csrf(request)
    await _revoke_session(request, db)
    secure = settings.AUTH_COOKIE_SECURE or settings.ENVIRONMENT.lower() in {
        "production",
        "staging",
    }
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        domain=settings.AUTH_COOKIE_DOMAIN or None,
        path="/",
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        domain=settings.AUTH_COOKIE_DOMAIN or None,
        path="/api/v1/auth",
        secure=secure,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME, domain=settings.AUTH_COOKIE_DOMAIN or None, path="/"
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_bearer(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    _require_csrf(request)
    await _revoke_session(request, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(require_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


async def _rotate_refresh_token(raw_token: str, db: AsyncSession) -> TokenResponse:
    payload = decode_access_token(raw_token, expected_type="refresh")
    if not payload or not payload.get("sid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    try:
        session_id = UUID(str(payload["sid"]))
        user_id = UUID(str(payload["sub"]))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc
    session = await db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    )
    if (
        session is None
        or session.expires_at <= datetime.now(timezone.utc)
        or not secrets.compare_digest(session.refresh_token_hash, hash_token(raw_token))
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    session.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return await _issue_token_pair(user, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    return await _rotate_refresh_token(payload.refresh_token, db)


@router.post("/web/refresh", response_model=WebSessionResponse)
async def refresh_web_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> WebSessionResponse:
    _require_csrf(request)
    raw_token = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_response = await _rotate_refresh_token(raw_token, db)
    _set_web_session(response, token_response.access_token, token_response.refresh_token)
    return WebSessionResponse(user=token_response.user)
