# ClearPath Nexus — Engineering Review (current)

> **ARCHIVED REVIEW.** “Current” refers to the earlier v2 review pass. Use `docs/PRODUCT_TRUTH.md` and `BUILD_REPORT.md` for v5.

## What this is

A three-client monorepo for a railway-freight route-planning platform:

- `backend/`: FastAPI, async SQLAlchemy, PostGIS, Redis, JWT/cookie
  authentication, Alembic migrations, structured logging, and honest-
  degradation provider adapters (weather, space weather, port sync,
  live corridor traffic).
- `frontend/`: React, TypeScript, Vite, Leaflet, Axios, deployable as a
  container or static site.
- `android/`: Kotlin, Jetpack Compose, Ktor, Kotlin serialization.

This is a competition/demo build, not a certified railway dispatch or
signalling system. It intentionally ships with demo route/weather/port
data — see "Known scope" below.

## Current state (as of this pass)

### Security
- Login is protected against a timing side-channel: unknown-email logins
  hash against a fixed dummy value so response time doesn't reveal whether
  an account exists.
- Web sessions use an httpOnly, SameSite cookie (`/auth/web/login`, `/web/
  register`, `/web/logout`) instead of a client-readable token. Android
  keeps a bearer-token flow, appropriate for a native client.
- A Content-Security-Policy header is set in the Caddy reverse-proxy config.
- Protected operational routes enforce the `operator` or `admin` role; the
  role is also carried in the short-lived access-token claims and rechecked
  against the database-backed session/user state.

### Data integrity
- Every external provider (weather, space weather, maritime berth sync,
  live corridor traffic) reports `unavailable`/`available: false` on
  failure and is scored/handled accordingly — none fabricate "all clear"
  data when a real fetch fails. This is covered by
  `backend/app/tests/test_provider_truth.py`.

### Infrastructure
- Alembic migrations exist and match the ORM models, including the
  `auth_sessions` table and operational indexes/foreign keys.
- `backend/Dockerfile` now runs `scripts/start.sh` (migrations, then
  optional demo-data seed, then the server) instead of skipping migrations.
- Structured JSON logging and a `ProviderStatusRegistry` track per-provider
  health, exposed at `GET /status/providers`.
- `DEMO_DATA_ENABLED` hard-fails startup if left `true` in prod/staging.

### CI
- `.github/workflows/ci.yml` runs backend pytest, frontend build/lint/audit,
  and Android debug+release builds on every push.

### Android
- Release signing is external: `assembleRelease` requires the gitignored
  `android/key.properties` and a keystore supplied by CI or a secret manager.
  CI uses `-PallowUnsignedRelease=true` only for compile verification; that
  flag must not be used for distribution.

### Optional live-data demo layer
- `backend/app/services/railradar.py` optionally integrates the RailRadar
  public developer sandbox for live passenger-train positions along a
  corridor, surfaced at `GET /railways/live-corridor-traffic` and in the
  web UI under the "Live Traffic" tab. Unset `RAILRADAR_API_KEY` (the
  default) means the endpoint returns `available: false` with an
  explanatory message; it never fabricates traffic. This covers
  passenger/PRS trains only and does not feed into the Route Reliability
  Index — it's a proof-of-concept live integration, not a freight-
  operations feed.

## Known scope (intentional, not bugs)

- `RAILWAY_OPERATIONS_FEED` and `MARITIME_BERTH_DATA_FEED` are unset by
  default. Licensing real Indian Railways freight data (CRIS/FOIS) and a
  maritime berth feed (MSW/PCS 1x) requires business-entity registration
  with those platforms — out of scope for a competition timeline. The app
  is explicit about this rather than faking the data.
- `docs/PRIVACY_POLICY_DRAFT.md`, `docs/TERMS_OF_SERVICE_DRAFT.md`, and
  `docs/PRODUCTION_RELEASE_CHECKLIST.md` are marked draft and would need
  real legal review before any production launch.
- Route Reliability Index weights are configurable via environment
  variables but not yet calibrated against real historical delay data.

## Verification notes

Verified in this workspace: backend compile, Ruff, 12 pytest tests, offline
Alembic SQL generation, frontend TypeScript, ESLint, and Vite production
build. The Python dependency audit reports no known vulnerabilities, and the
frontend production audit reports no known vulnerabilities. Docker is not
installed on this host, and Java/Gradle is not available, so Docker image /
Compose startup and Android builds remain CI or deployment-host gates.
