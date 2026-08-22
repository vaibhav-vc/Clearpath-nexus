# ClearPath Nexus — change summary

## v5.2 — LiveOps and production ML foundation

- Added a normalized live-data envelope, validation, freshness, bounded retry/backoff, circuit breaking, durable observations, Redis latest-value cache, provider runtime state, and a single live-ingestor worker.
- Added route-length-aware weather sampling (three to five corridor points) with conservative deterministic aggregation.
- Added persisted operational events, authenticated event APIs/SSE, provider/weather event generation, and lifecycle updates.
- Added owner-scoped, explicit and stoppable shipment tracking with SourceLine position evidence.
- Added the LiveOps web control center and kept it lazy-loaded.
- Added dataset, training-run, model-version, and prediction registries plus the first remaining-delay regression pipeline.
- Added chronological split, leakage checks, deterministic baseline comparison, checksummed trusted artifacts, candidate/production gates, outcome labels, prediction lineage, low-cardinality metrics, and deterministic fallback.
- Added Alembic revision `20260822_06`, Docker live-ingestor service, v5.2 provider smoke script, documentation, tests, and 5.2.0 metadata.

## v5.1 — super-final correctness and efficiency audit

- Resolved all 11 findings from an independent Bugbot review.
- Parallelized route weather, NOAA, port, and congestion lookups; parallelized alternate-route weather calls.
- Preserved real cached/stale RailRadar and AIS states and observation timestamps.
- Made port evidence reproducible with window, evaluation, arrival, berth, and vessel inputs.
- Corrected unavailable NOAA lineage to `EXCLUDED_FROM` and included raw ancestors in evidence components.
- Prevented empty document placeholders from satisfying ComplianceGuard requirements.
- Tied documents to their exact check and added append-only override events through migration `20260822_05`.
- Paginated and batch-loaded compliance history instead of unbounded N+1 queries.
- Normalized metrics paths to prevent UUID-driven cardinality growth.
- Replaced browser-local Audit history with owner-scoped backend route IDs and stored evidence inspection.
- Lazy-loaded web modules, reducing the initial JavaScript chunk below the build warning threshold.

## v5.0 — SourceLine + ComplianceGuard

- Added immutable, owner-scoped route decision snapshots and provenance records.
- Added source catalog, normalized source states, timestamp-based freshness, real traceability counts, checksums, transformations, exclusions, and lineage edges.
- Route evaluation/suggestion now commits evidence atomically and returns a compact provenance summary.
- Added historical evidence, record-neighborhood, source catalog, and provider-health APIs under `/api/v1/provenance`.
- Added deterministic ComplianceGuard checks, operator document metadata, expiry-versus-ETA review, rule-source versioning, and reasoned override audit APIs.
- Added web evidence inspection, Source Trust Center, and ComplianceGuard screens.
- Added Android provenance-summary support and removed repository-embedded Supabase project defaults.
- Added Alembic revision `20260822_04` and unit tests for freshness, traceability, unavailable sources, secret redaction, permit expiry, physical blocks, and override validation.

The older session notes below are retained for history and may describe an earlier repository state.

All work from this session. 76 tests passing across 5 suites.

## 1. Auth — Supabase issues, backend verifies

- `backend/app/core/security.py` — was a one-line stub. Now verifies Supabase
  JWTs via JWKS (asymmetric, no shared secret), with HS256 fallback for legacy
  projects.
- All `/planner/*` and `/port/*` endpoints now require a valid token.
- `AUTH_DISABLED` dev escape hatch — raises if `ENVIRONMENT=production`.
- New dep: `pyjwt[crypto]`.

## 2. Port sync — stopped reporting fabricated data

- `backend/app/services/port_sync.py` rewritten. The silent
  `except -> MOCK_BERTH` fallback is gone.
- Every result carries `LIVE_FEED` / `OPERATOR_INPUT` / `UNAVAILABLE`.
- `reliability.py`: when port data is missing it is EXCLUDED and the remaining
  weights renormalise, rather than scoring as zero. This was a 22-point error.
- Requests may supply `loading_window` for a genuine port alignment score.

## 3. Android — backend for features, Supabase for auth

- `data/api/ApiClient.kt` (new) — Ktor client; lifts the access token off the
  live Supabase session.
- `data/api/ApiDtos.kt` (new) — wire types kept separate from domain models.
- `data/repository/NexusRepository.kt` — backend-first; `DemoRouteEngine`
  demoted to offline fallback. Results return `Sourced<T>` with
  `computedOffline` so the UI can say which it got.
- `res/xml/network_security_config.xml` (new) — cleartext allowed for local
  dev hosts only; production stays HTTPS-only.
- `build.gradle.kts` — `BuildConfig.API_BASE_URL` per build type, Ktor JSON deps.

## 4. Live corridor data (free tiers only)

- `services/live_rail.py` (new) — RailRadar corridor delays.
  Free tier is 1,000 req/month, so the 2h cache and budget counter are
  load-bearing, not optimisations.
- `services/live_port.py` (new) — aisstream.io AIS vessel activity at JNPT.
  NOTE: AIS gives CONGESTION, never a berth schedule.
- `services/congestion.py` (new) — blends live readings with the seeded
  baseline (default weight 0.6). Port penalty applies only to port-bound
  routes and caps at 25 points.
- `api/v1/live.py` (new) — `/live/corridor-congestion`, `/live/port-activity`.
- `scripts/smoke_live_feeds.py` (new) — exercises both real providers.

## Bugs found and fixed while testing

1. Malformed API response scored the corridor 100/100 CLEAR.
2. Failed requests burned RailRadar quota — a flaky network drained the whole
   monthly allowance without one successful call.
3. `int(None)` on a malformed AIS frame killed the collector loop.
4. AIS `@` name padding not stripped (`MAERSK KOLKATA@@@@@@`).
5. A wrong expected value in my own parity vector — caught by the test.

## Running it

    cd backend
    pip install -r requirements.txt
    # set SUPABASE_URL, RAILRADAR_API_KEY, AISSTREAM_API_KEY in .env
    pytest app/tests/
    python scripts/smoke_live_feeds.py

Android: Gradle sync (two new Ktor artifacts), then run.

## Not verified here

Live connectivity — the build sandbox had no outbound network. Parsing,
scoring, caching, budget and failure handling are proven against fixtures in
`app/tests/fixtures/`. Confirm the real endpoints with the smoke script.

## Still open

- Kotlin-side scoring parity test (Python vectors are in `test_scoring_parity.py`)
- `alembic init` — Alembic is already in requirements, no migrations exist
- README still says Leaflet + PostgreSQL; actual stack is Google Maps + Supabase
- `mobile/` (React Native) has no `package.json` and cannot build — revive or delete
- RLS on `route_evaluations` — client writes to it directly with the anon key
