# ClearPath Nexus v6.0

ClearPath Nexus is an explainable freight operations intelligence and decision-support platform combining rail-route feasibility, cargo clearance, environmental risk, congestion, port coordination, scheduling, information provenance, compliance review, and dispatch lifecycle management.

It is not railway signalling, Kavach/ATP, electronic interlocking, official dispatch control, customs authority, a certified engineering source, or legal authority. Qualified humans retain final operational and legal responsibility.

## What is implemented

- Supabase-issued authentication tokens verified by FastAPI; operational records remain backend-authorized and owner-scoped.
- `/api/v1` FastAPI API with Postgres/PostGIS, SQLAlchemy 2, Redis, Alembic, WebSockets, health/readiness, and metrics.
- Deterministic cargo height, width, and weight clearance. A physical failure produces `HARD_BLOCKED` and overrides the numerical route score.
- Dijkstra rail routing, route evaluation/suggestion/history, dispatch, train schedules, and conflict detection.
- Deterministic reliability scoring using weather, congestion, historical baseline, and port alignment. Missing port data is excluded and weights are renormalized.
- Open-Meteo/OpenWeather weather adapters, NOAA SWPC supplemental telemetry, optional RailRadar/AIS signals, explicit provider-health states, and honest unavailable states.
- Nexus SourceLine: immutable decision snapshots, normalized source types, freshness, checksums, decision use/exclusion, lineage edges, source catalog, traceability counts, and historical evidence APIs.
- Nexus ComplianceGuard: deterministic document completeness, document/permit expiry versus ETA, declaration and approval checks, rule-source versioning, owner-scoped history, and reasoned override audit records.
- LiveOps: normalized provider envelopes, durable observations, Redis latest-value cache, circuit breakers, a single background ingestor, operational events/SSE, explicit shipment tracking consent, and an owner-scoped control center.
- Production ML foundation: versioned datasets/training runs/models/predictions, chronological splits, leakage checks, deterministic benchmarking, checksummed artifacts, promotion gates, SourceLine prediction evidence, and deterministic fallback.
- Predictive Intelligence v5.3: empirical intervals that fail closed without trusted calibration, exact deterministic factor decomposition, owner-scoped drift monitoring, and manual-only retraining readiness.
- Multimodal v5.4: operator/provider-evidence plans across road, rail, port, and sea legs with continuity validation, per-leg ETA/cost/risk/compliance/source state, hard-block precedence, counted traceability, lineage, and immutable input snapshots.
- Integrated Operations v6: one owner-scoped overview across routes, schedules, shipments, events, compliance, predictive ETA, multimodal plans, providers, audit export, and an explicitly limited shipment-state projection.
- Optional authorized ixigo train synchronization with a fail-closed `AUTH_REQUIRED` state, whitelisted passenger-status fields, SourceLine evidence, schedule ownership checks, manual sync API, and a separately enabled worker profile. It is never freight authority or train control.
- Concurrent provider resolution, route-specific client time budgets, normalized low-cardinality metrics paths, paginated/batched compliance history, and lazy-loaded web modules.
- React 19/Vite/Tailwind/Leaflet web operations console, Source Trust Center, evidence drawer, and ComplianceGuard review.
- Kotlin/Compose Android client using Supabase auth and FastAPI operational APIs. Local fallback is labelled `OFFLINE_COMPUTED`.

See [product truth](docs/PRODUCT_TRUTH.md), [LiveOps](docs/LIVEOPS.md), [ML](docs/ML.md), [multimodal/v6](docs/MULTIMODAL_V6.md), [ixigo synchronization](docs/IXIGO_TRAIN_SYNC.md), [SourceLine](docs/SOURCELINE.md), [ComplianceGuard](docs/COMPLIANCEGUARD.md), and [provider attribution](docs/DATA_SOURCES_AND_ATTRIBUTION.md).

## Quick start

Copy `.env.example` to `.env` and provide your own Supabase project settings. Never expose a Supabase service-role key to either client.

```powershell
docker compose up --build
```

Apply database migrations before starting a newly upgraded environment:

```powershell
cd backend
alembic upgrade head
```

Android reads `backendBaseUrl`, `supabaseUrl`, and `supabaseAnonKey` Gradle properties. Repository defaults are non-secret placeholders; configure values locally in `~/.gradle/gradle.properties` or secured CI.

## Verification

```powershell
cd backend
python -m pytest -q
ruff check .

cd ..\frontend
pnpm install
pnpm run build
pnpm run lint
```

Android requires a locally installed JDK and Android SDK: `gradlew testDebugUnitTest assembleDebug`.

The live ingestor runs separately from API requests:

```powershell
cd backend
python -m app.workers.live_ingestor
```

The ixigo adapter has no default consumer endpoint. Only users with separately authorized partner access should configure `IXIGO_TRAIN_STATUS_URL`, `IXIGO_API_KEY`, and `IXIGO_SYNC_ENABLED=true`, then start its isolated profile:

```powershell
docker compose --profile ixigo up --build train-synchronizer
```

Without those credentials, train sync truthfully returns `AUTH_REQUIRED`; route planning and scheduling continue normally.

Build and evaluate the first delay-model candidate only after the schema is migrated:

```powershell
python scripts/build_ml_dataset.py --include-simulated --register
python scripts/train_delay_model.py --register
python scripts/evaluate_delay_model.py
```

`--include-simulated` is strictly a pipeline-validation path. The generated rows are labelled `SIMULATED`, remain ineligible for production evaluation, and cannot pass the promotion gate.

## Data honesty

Source states distinguish `LIVE_PROVIDER`, `PUBLIC_OPEN_DATA`, `CACHED_PROVIDER`, `OPERATOR_INPUT`, `SEEDED_BASELINE`, `DERIVED`, `SIMULATED`, `OFFLINE_COMPUTED`, `IMPORTED_DOCUMENT`, and `UNAVAILABLE`. Provider-specific raw states remain stored separately.

The current segment engineering constraints, static congestion values, and historical-delay factors are seeded demonstration baselines. OpenStreetMap geometry does not certify bridge/OHE clearances, structure gauge, or axle-load capacity. ComplianceGuard is decision support, not legal advice, and it never invents penalty amounts.

## Project layout

- `backend/` — FastAPI, SQLAlchemy/PostGIS, Alembic, deterministic services, and pytest suite.
- `frontend/` — React 19 operations console.
- `android/` — Kotlin/Jetpack Compose client.
- `docs/` — product truth, evidence model, compliance scope, and source attribution.

## License

Project code is provided under [MIT](LICENSE). External datasets and providers retain their own terms and attribution requirements.
