from typing import Literal
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = ""
    PROJECT_NAME: str = "ClearPath Nexus Engine"
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    AUTH_COOKIE_NAME: str = "clearpath_session"
    AUTH_REFRESH_COOKIE_NAME: str = "clearpath_refresh"
    CSRF_COOKIE_NAME: str = "clearpath_csrf"
    AUTH_COOKIE_DOMAIN: str | None = None
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    DEMO_DATA_ENABLED: bool = False

    # Supabase owns user registration, sign-in, refresh, and password policy.
    # The API only verifies the access tokens it issues.
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    AUTH_DISABLED: bool = False

    POSTGRES_USER: str = "clearpath_user"
    POSTGRES_PASSWORD: str = "change_me"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "clearpath_nexus_db"
    DATABASE_URL: str = ""

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    OPENWEATHER_API_KEY: str = ""
    NOAA_SPACE_WEATHER_FEED_URL: str = (
        "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    )
    MARITIME_BERTH_DATA_FEED: str = ""
    MARITIME_FEED_API_KEY: str = ""
    RAILWAY_OPERATIONS_FEED: str = ""
    RAILWAY_FEED_API_KEY: str = ""
    ROUTE_RETENTION_DAYS: int = 90

    # Optional demo-mode live data source (RailRadar free developer sandbox).
    # Covers passenger/PRS train positions, NOT freight consists — do not
    # treat this as a substitute for RAILWAY_OPERATIONS_FEED. Purely additive:
    # the app runs identically with this unset.
    RAILRADAR_API_KEY: str = ""
    RAILRADAR_BASE_URL: str = "https://api.railradar.in/v1"
    RAILRADAR_CACHE_TTL_SECONDS: int = 7200
    RAILRADAR_MONTHLY_BUDGET: int = 900
    # ixigo does not publish an open developer API in the supplied/current
    # evidence. These settings are only for a separately authorized partner
    # or customer gateway; no private consumer endpoint is scraped.
    IXIGO_TRAIN_STATUS_URL: str = ""
    IXIGO_API_KEY: str = ""
    IXIGO_SYNC_ENABLED: bool = False
    IXIGO_SYNC_INTERVAL_SECONDS: int = 900
    AISSTREAM_API_KEY: str = ""
    AIS_COLLECTOR_ENABLED: bool = True
    LIVE_CONGESTION_ENABLED: bool = True
    LIVE_CONGESTION_WEIGHT: float = 0.6

    LIVE_DATA_ENABLED: bool = True
    ENABLE_LIVE_WEATHER: bool = True
    ENABLE_LIVE_RAIL: bool = True
    ENABLE_LIVE_AIS: bool = False
    ENABLE_LIVE_GPS: bool = True
    ENABLE_EVENT_ENGINE: bool = True
    ENABLE_ML_INFERENCE: bool = True
    LIVE_INGEST_INTERVAL_SECONDS: int = 600
    LIVE_OBSERVATION_CACHE_SECONDS: int = 900
    LIVE_OBSERVATION_RETENTION_DAYS: int = 30
    POSITION_RETENTION_DAYS: int = 14
    PROVIDER_TIMEOUT_SECONDS: float = 8.0
    PROVIDER_MAX_RETRIES: int = 2
    PROVIDER_FAILURE_THRESHOLD: int = 3
    PROVIDER_CIRCUIT_COOLDOWN_SECONDS: int = 120
    MODEL_ARTIFACT_ROOT: str = "artifacts/models"

    WEIGHT_WEATHER_RISK: float = 0.40
    WEIGHT_PORT_ALIGNMENT: float = 0.30
    WEIGHT_CORRIDOR_CONGESTION: float = 0.15
    WEIGHT_HISTORICAL_DELAY: float = 0.15

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://10.0.2.2:8000",
    ]
    REGISTRATION_ENABLED: bool = False
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_WINDOW_SECONDS: int = 60
    REGISTRATION_RATE_LIMIT: int = 3
    REGISTRATION_RATE_WINDOW_SECONDS: int = 3600
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "10.0.2.2", "testserver"]


settings = Settings()

if settings.ENVIRONMENT.lower() in {"production", "staging"} and len(settings.SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be configured with at least 32 characters")

if settings.ENVIRONMENT.lower() in {"production", "staging"} and settings.DEMO_DATA_ENABLED:
    raise RuntimeError("DEMO_DATA_ENABLED must be false outside development")

if settings.ENVIRONMENT.lower() in {"production", "staging"} and settings.AUTH_DISABLED:
    raise RuntimeError("AUTH_DISABLED must be false outside development")

if settings.AUTH_COOKIE_SAMESITE == "none" and not settings.AUTH_COOKIE_SECURE:
    raise RuntimeError("AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE=none")

if any(origin == "*" for origin in settings.CORS_ORIGINS):
    raise RuntimeError("CORS_ORIGINS cannot contain '*' when credentialed sessions are enabled")

if settings.ACCESS_TOKEN_EXPIRE_MINUTES < 5:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 5")

if settings.REFRESH_TOKEN_EXPIRE_DAYS < 1:
    raise RuntimeError("REFRESH_TOKEN_EXPIRE_DAYS must be at least 1")

if settings.LIVE_OBSERVATION_RETENTION_DAYS < 1:
    raise RuntimeError("LIVE_OBSERVATION_RETENTION_DAYS must be at least 1")

if settings.POSITION_RETENTION_DAYS < 1:
    raise RuntimeError("POSITION_RETENTION_DAYS must be at least 1")

if (
    abs(
        settings.WEIGHT_WEATHER_RISK
        + settings.WEIGHT_PORT_ALIGNMENT
        + settings.WEIGHT_CORRIDOR_CONGESTION
        + settings.WEIGHT_HISTORICAL_DELAY
        - 1.0
    )
    > 0.001
):
    raise RuntimeError("Route reliability weights must sum to 1.0")

if not settings.DATABASE_URL:
    settings.DATABASE_URL = (
        f"postgresql+asyncpg://{quote(settings.POSTGRES_USER, safe='')}:{quote(settings.POSTGRES_PASSWORD, safe='')}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{quote(settings.POSTGRES_DB, safe='')}"
    )
