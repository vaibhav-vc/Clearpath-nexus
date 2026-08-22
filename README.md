# ClearPath Nexus v6.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20%2B%20Postgres%2FPostGIS-009688)](backend)
[![Frontend](https://img.shields.io/badge/frontend-React%2019%20%2B%20Vite-61DAFB)](frontend)
[![Android](https://img.shields.io/badge/android-Kotlin%20%2F%20Compose-3DDC84)](android)

ClearPath Nexus is an explainable freight operations intelligence and decision-support platform combining rail-route feasibility, cargo clearance, environmental risk, congestion, port coordination, scheduling, information provenance, compliance review, and dispatch lifecycle management.

> **Scope.** It is not railway signalling, Kavach/ATP, electronic interlocking, official dispatch control, customs authority, a certified engineering source, or legal authority. Qualified humans retain final operational and legal responsibility.

## Table of contents

- [What is implemented](#what-is-implemented)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Verification](#verification)
- [Data honesty](#data-honesty)
- [From the original concept to v6.0](#from-the-original-concept-to-v60)
- [Project layout](#project-layout)
- [Documentation](#documentation)
- [License](#license)

## What is implemented

**Core routing & compliance**
- Supabase-issued authentication tokens verified by FastAPI; operational records remain backend-authorized and owner-scoped.
- `/api/v1` FastAPI API with Postgres/PostGIS, SQLAlchemy 2, Redis, Alembic, WebSockets, health/readiness, and metrics.
- Deterministic cargo height, width, and weight clearance. A physical failure produces `HARD_BLOCKED` and overrides the numerical route score.
- Dijkstra rail routing, route evaluation/suggestion/history, dispatch, train schedules, and conflict detection.
- Deterministic reliability scoring using weather, congestion, historical baseline, and port alignment. Missing port data is excluded and weights are renormalized.

**Data & provenance**
- Open-Meteo/OpenWeather weather adapters, NOAA SWPC supplemental telemetry, optional RailRadar/AIS signals, explicit provider-health states, and honest unavailable states.
- **Nexus SourceLine** — immutable decision snapshots, normalized source types, freshness, checksums, decision use/exclusion, lineage edges, source catalog, traceability counts, and historical evidence APIs.
- **Nexus ComplianceGuard** — deterministic document completeness, document/permit expiry versus ETA, declaration and approval checks, rule-source versioning, owner-scoped history, and reasoned override audit records.
- **LiveOps** — normalized provider envelopes, durable observations, Redis latest-value cache, circuit breakers, a single background ingestor, operational events/SSE, explicit shipment tracking consent, and an owner-scoped control center.

**Machine learning & prediction**
- Production ML foundation: versioned datasets/training runs/models/predictions, chronological splits, leakage checks, deterministic benchmarking, checksummed artifacts, promotion gates, SourceLine prediction evidence, and deterministic fallback.
- **Predictive Intelligence v5.3** — empirical intervals that fail closed without trusted calibration, exact deterministic factor decomposition, owner-scoped drift monitoring, and manual-only retraining readiness.
- **Multimodal v5.4** — operator/provider-evidence plans across road, rail, port, and sea legs with continuity validation, per-leg ETA/cost/risk/compliance/source state, hard-block precedence, counted traceability, lineage, and immutable input snapshots.
- **Integrated Operations v6** — one owner-scoped overview across routes, schedules, shipments, events, compliance, predictive ETA, multimodal plans, providers, audit export, and an explicitly limited shipment-state projection.

**Integrations & clients**
- Optional authorized ixigo train synchronization with a fail-closed `AUTH_REQUIRED` state, whitelisted passenger-status fields, SourceLine evidence, schedule ownership checks, manual sync API, and a separately enabled worker profile. It is never freight authority or train control.
- Concurrent provider resolution, route-specific client time budgets, normalized low-cardinality metrics paths, paginated/batched compliance history, and lazy-loaded web modules.
- React 19/Vite/Tailwind/Leaflet web operations console, Source Trust Center, evidence drawer, and ComplianceGuard review.
- Kotlin/Compose Android client using Supabase auth and FastAPI operational APIs. Local fallback is labelled `OFFLINE_COMPUTED`.

## Architecture

```
┌──────────────┐     ┌──────────────┐
│ React Web    │     │ Android      │
│ Console      │     │ (Kotlin/     │
│ (Vite/       │     │  Compose)    │
│  Tailwind)   │     │              │
└──────┬───────┘     └──────┬───────┘
       │      Supabase auth │
       └─────────┬──────────┘
                  ▼
          ┌───────────────┐
          │ FastAPI        │  /api/v1
          │ (SQLAlchemy 2) │  health · readiness · metrics
          └───────┬────────┘
                  │
   ┌──────────────┼───────────────────────┐
   ▼              ▼                       ▼
Postgres/     Redis (cache,        Background workers
PostGIS       circuit breakers)    (live ingestor, ixigo sync)
   │                                       │
   ▼                                       ▼
Alembic migrations              External providers (weather,
                                 NOAA SWPC, RailRadar/AIS, ixigo)
```

Every routing, clearance, compliance, and prediction decision is backed by a SourceLine-tracked evidence trail rather than an opaque score.

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

## From the original concept to v6.0

The project began as "AI-Powered Railway Intelligence Command Center", an MVP concept covering route planning, environmental risk, port synchronization, and reliability scoring. Much of that survived intact. Some of it changed once the system had to defend its own numbers, and a good deal was added that the original scope never described.

### Carried over unchanged

The Route Reliability Index still weights exactly as originally specified — weather `0.40`, port alignment `0.30`, congestion `0.15`, historical delay `0.15` — and those values live in `backend/app/core/config.py` today. A failed physical clearance check still overrides the numerical score outright rather than degrading it. Cargo clearance validation, weather and dust-storm intelligence, space-weather telemetry, port synchronization, the interactive Leaflet map, the threat simulator, and the React/FastAPI/Postgres/MIT foundation all shipped as described.

### Changed in practice

| Original concept | v6.0 as built |
| --- | --- |
| Route marked `BLOCKED` | `HARD_BLOCKED`, which overrides the numerical score rather than sitting alongside it |
| PostgreSQL | Postgres + **PostGIS** for geospatial work, plus **Redis** for provider caching and circuit breakers |
| `npm install` / `npm run dev` at the repository root | **pnpm** inside `frontend/`, or `docker compose up --build` for the whole stack |
| `database/` directory for schema and migrations | Alembic migrations under `backend/alembic` |
| React | React 19 |
| Phase 3: "AI Delay Prediction" | The ML pipeline exists — versioned datasets, training runs, benchmarking, promotion gates — but **every registered model is still a `CANDIDATE`**. Deterministic prediction remains in control, because the promotion gates require real operational rows and the current dataset is entirely simulated. |

### Added beyond the original scope

Nothing in the original concept described where a number came from. Most of what v6 adds exists to answer that:

- **Nexus SourceLine** — immutable decision snapshots, lineage edges, checksums, and traceability counts
- **Nexus ComplianceGuard** — document and permit checks, rule-source versioning, reasoned override audit records
- **LiveOps** — durable observations, provider circuit breakers, operational events, an owner-scoped control center
- **Multimodal v5.4** — road, rail, port, and sea legs with continuity validation and per-leg evidence
- **Integrated Operations v6** — one owner-scoped view across every subsystem
- **Supabase authentication** with backend-authorized, owner-scoped records
- **A Kotlin/Compose Android client**, with local fallback explicitly labelled `OFFLINE_COMPUTED`
- **The source-state vocabulary** described under [Data honesty](#data-honesty), so an unavailable provider reports itself instead of being quietly filled in
- **Optional ixigo train synchronization**, fail-closed at `AUTH_REQUIRED` and never treated as freight authority

### Still out of scope

Unchanged from the original decision: track maintenance forecasting, rail wear prediction, locomotive health monitoring, passenger booking, crew scheduling, and ticketing integrations. The focus remains freight decision support.

## Project layout

| Path | Description |
| --- | --- |
| `backend/` | FastAPI, SQLAlchemy/PostGIS, Alembic, deterministic services, and pytest suite. |
| `frontend/` | React 19 operations console. |
| `android/` | Kotlin/Jetpack Compose client. |
| `docs/` | Product truth, evidence model, compliance scope, and source attribution. |

## Documentation

| Topic | Doc |
| --- | --- |
| Product scope and truthfulness constraints | [PRODUCT_TRUTH.md](docs/PRODUCT_TRUTH.md) |
| Live data ingestion, circuit breakers, control center | [LIVEOPS.md](docs/LIVEOPS.md) |
| ML datasets, training, promotion gates | [ML.md](docs/ML.md) |
| Multimodal v6 planning | [MULTIMODAL_V6.md](docs/MULTIMODAL_V6.md) |
| ixigo train synchronization | [IXIGO_TRAIN_SYNC.md](docs/IXIGO_TRAIN_SYNC.md) |
| SourceLine evidence and lineage model | [SOURCELINE.md](docs/SOURCELINE.md) |
| ComplianceGuard rules and audit trail | [COMPLIANCEGUARD.md](docs/COMPLIANCEGUARD.md) |
| Provider attribution and terms | [DATA_SOURCES_AND_ATTRIBUTION.md](docs/DATA_SOURCES_AND_ATTRIBUTION.md) |
| Deployment | [DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Production release checklist | [PRODUCTION_RELEASE_CHECKLIST.md](docs/PRODUCTION_RELEASE_CHECKLIST.md) |

## License

Project code is provided under [MIT](LICENSE). External datasets and providers retain their own terms and attribution requirements.
