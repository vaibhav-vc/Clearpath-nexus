# ClearPath Nexus v4.1 — Combined Build

> **ARCHIVED MERGE REPORT.** This records the earlier v4.1 consolidation. See `CHANGES.md` and `BUILD_REPORT.md` for v5.

This build combines the strongest production and feature work from all five supplied archives.

## Included

- Supabase sign-in/session handling on web and Android.
- Supabase JWT verification on every protected FastAPI feature route.
- Route planning, clearance validation, alternate routing, weather, port alignment, and threat simulation.
- User-scoped route history, route dispatch, train scheduling, conflict detection, and dispatch history.
- Predictive delay, dust-storm intelligence, analytics, track geometry, Indian Railways adapters, and live corridor traffic.
- Honest provider degradation, request metrics, health/readiness endpoints, rate limiting, data retention, Alembic migrations, CI, Docker, Caddy, and Android release-signing support.

## Required configuration

Copy `.env.example` to `.env` and set at minimum:

- `POSTGRES_PASSWORD`
- `SECRET_KEY` (32+ random characters for production)
- `SUPABASE_URL`
- `VITE_SUPABASE_URL` (normally the same URL)
- `VITE_SUPABASE_ANON_KEY`
- `CORS_ORIGINS`

Modern Supabase projects use JWKS automatically. Set `SUPABASE_JWT_SECRET` only for a legacy HS256 project.

For Android, pass `-PsupabaseUrl=...` and `-PsupabaseAnonKey=...` to Gradle when using a project other than the preserved original Supabase project. Set `-PbackendBaseUrl=...` for debug and `-PreleaseBackendBaseUrl=https://.../api/v1` for release.

## Verified

- Frontend TypeScript + Vite production build: passed.
- Frontend ESLint: passed.
- Backend source compilation: passed.
- Backend Ruff: passed.
- Backend pytest: 98 passed.

Android sources and Gradle configuration were merged and statically audited. A local Android compile still requires Android Studio/JDK/SDK, which was not installed in the merge environment.
