# Production Release Checklist

ClearPath Nexus must remain in staging until every required data, security, and legal item below has a named owner and dated approval.

## Hard launch gates

- [ ] Contract and activate an authorized Indian railway infrastructure/clearance dataset.
- [ ] Contract and activate an authorized live train-position and timetable feed through `RAILWAY_OPERATIONS_FEED`.
- [ ] Contract and activate an authorized berth/sailing provider through `MARITIME_BERTH_DATA_FEED`.
- [ ] Receive legal approval for each provider's permitted routing and reliability use.
- [ ] Calibrate Route Reliability Index weights against real historical delay data.
- [ ] Complete operator acceptance testing; do not use Nexus for signalling, dispatch, collision avoidance, or safety-critical control.

## Deployment configuration

- [ ] Use managed PostgreSQL/PostGIS and Redis with private networking, encryption, backups, and a tested restore.
- [ ] Run `alembic upgrade head` before starting the API; production startup performs this automatically.
- [ ] Set `ENVIRONMENT=production`, `DEMO_DATA_ENABLED=false`, a 32+ character `SECRET_KEY`, and strong database credentials.
- [ ] Set exact `CORS_ORIGINS`, `DOMAIN`, `AUTH_COOKIE_SECURE=true`, and an HTTPS Android `releaseBackendBaseUrl`.
- [ ] Keep `REGISTRATION_ENABLED=false` unless invitation and verification controls have been approved.
- [ ] Rotate and remove `BOOTSTRAP_ADMIN_PASSWORD` after the first administrator login.
- [ ] Store Android signing keystore and all deployment secrets only in CI/hosting secret managers.

## Operational readiness

- [ ] Monitor `/ready` and `/status/providers`; alert on a provider becoming unavailable or stale.
- [ ] Enable centralized JSON log collection and request-ID correlation.
- [ ] Run authenticated `/planner/evaluate`, `/planner/suggest`, and `/planner/simulate` load tests against staging PostGIS/Redis.
- [ ] Commission independent penetration testing and legal/privacy review.
- [ ] Publish reviewed Terms of Service, Privacy Policy, support contacts, and Play Store data-safety declarations.
- [ ] Define and implement the retention/deletion schedule for `GeneratedRoute` records.

## Verification commands

```powershell
cd backend
python -m compileall app scripts alembic
python -m pytest -q

cd ../frontend
npm ci
npm run build
npm run lint
npm audit --omit=dev --audit-level=high

cd ../android
.\gradlew.bat :app:assembleDebug :app:assembleRelease -PreleaseBackendBaseUrl=https://api.example.invalid/api/v1 --no-daemon
```

The release is not approved until the hard launch gates are signed off.
