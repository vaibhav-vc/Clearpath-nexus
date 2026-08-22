# ClearPath Nexus deployment

This document is the operational runbook for the V4 tree. The application is
not a signalling, dispatch, collision-avoidance, or safety-critical control
system.

## Local Docker development

```sh
cp .env.example .env
# Set POSTGRES_PASSWORD, SECRET_KEY, BOOTSTRAP_ADMIN_EMAIL, and
# BOOTSTRAP_ADMIN_PASSWORD in .env.
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

The development template enables `DEMO_DATA_ENABLED=true`, which seeds the
demo corridor and administrator. Keep that value false in staging and
production. The local web application is at `http://localhost:5173` and the
API is at `http://localhost:8000`.

## Production Docker deployment

Use managed PostgreSQL/PostGIS and Redis where possible. Put `.env` in the
deployment secret store and set at minimum:

- `ENVIRONMENT=production`
- `DEMO_DATA_ENABLED=false`
- a random `SECRET_KEY` of at least 32 characters
- strong database credentials
- exact HTTPS `CORS_ORIGINS`
- `ALLOWED_HOSTS` for the edge/API hostnames
- `AUTH_COOKIE_SECURE=true`
- `DOMAIN` for Caddy
- authorized `MARITIME_BERTH_DATA_FEED` and `RAILWAY_OPERATIONS_FEED`

Then start the production profile:

```sh
docker compose --profile https -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose --profile https -f docker-compose.yml -f docker-compose.prod.yml ps
curl -f https://$DOMAIN/health
```

The backend runs Alembic migrations before serving traffic. It does not seed
demo rows when `DEMO_DATA_ENABLED=false`. Configure backups, restore tests,
private database/Redis networking, TLS certificates, centralized logs, and
monitoring for `/ready` and `/status/providers` before launch.

## Direct backend/frontend verification

```sh
cd backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m compileall app scripts alembic
.venv/bin/ruff check app scripts alembic
.venv/bin/python -m pytest -q

cd ../frontend
npm ci
npm run typecheck
npm run lint
npm run build
npm audit --omit=dev --audit-level=high
```

The canonical frontend lockfile is `frontend/package-lock.json`; use npm in
CI and release environments.

## Authentication smoke tests

The web client uses httpOnly access/refresh cookies plus a readable,
double-submit CSRF cookie/header. Native Android uses bearer access and
rotating refresh tokens.

```sh
curl -i -c /tmp/nexus.cookies \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"replace_with_a_long_bootstrap_password"}' \
  http://localhost:8000/api/v1/auth/web/login

curl -b /tmp/nexus.cookies http://localhost:8000/api/v1/auth/me
```

Do not use public registration in production unless invitation, verification,
and abuse controls are approved. Rotate and remove the bootstrap password
after the first administrator login.

## Android release

```sh
cd android
./gradlew assembleDebug -PbackendBaseUrl=http://10.0.2.2:8000/api/v1 --no-daemon
./gradlew assembleRelease -PreleaseBackendBaseUrl=https://api.example.com/api/v1 --no-daemon
```

The release command requires `android/key.properties` and an external
keystore. The repository intentionally contains neither. CI may use
`-PallowUnsignedRelease=true` to verify compilation only; never distribute an
unsigned APK.

## Current launch gates

The platform remains staging-only until authorized railway infrastructure,
freight operations, and maritime berth feeds are contracted and legally
approved; reliability weights are calibrated; operator acceptance testing and
independent security testing are complete; and the draft legal documents are
reviewed and published.
