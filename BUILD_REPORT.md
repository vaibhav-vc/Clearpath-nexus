# ClearPath Nexus v6.0 super-final build report

Date: 22 August 2026

## Executive summary

The supplied v5.1 baseline was extended incrementally through v5.2 LiveOps, v5.3 Predictive Intelligence, v5.4 multimodal planning, and a bounded v6 integrated-operations release. Existing route evaluation, Supabase-issued authentication, FastAPI authorization, SourceLine, ComplianceGuard, scheduling, dispatch, web, Android, and deterministic safety logic were preserved.

This remains an explainable freight decision-support platform. It is not railway signalling, Kavach/ATP, interlocking, official dispatch control, certified engineering authority, customs authority, legal authority, or autonomous train control.

## Delivered

### v5.2 LiveOps and production ML foundation

- Normalized provider envelopes, validation, bounded retries, circuit breakers, freshness, cache state, checksums, durable observations, provider runtime state, Redis latest-value caching, and one background ingestor.
- Live Open-Meteo and NOAA SWPC adapters; RailRadar/AIS remain optional and explicitly unavailable without legitimate access.
- Persisted operational events, authenticated SSE, lifecycle actions, explicit shipment tracking consent, retention, and a lazy-loaded LiveOps web console.
- Route-weather sampling at three or five corridor points with concurrent provider resolution and worst-point conservative scoring.
- Versioned ML datasets, training runs, model versions, predictions, chronological splitting, leakage checks, checksummed artifacts, deterministic fallback, and promotion gates.

### v5.3 Predictive Intelligence

- Four CPU-safe candidate regressors benchmarked using validation-only model selection and one temporal test evaluation.
- Empirical 90% intervals fail closed unless at least 30 held-out calibration labels are entirely curated `REAL_LIVE`/`REAL_HISTORICAL` outcomes. Operator-confirmed labels remain research/audit evidence and cannot satisfy production trust gates.
- Exact deterministic contribution decomposition; when ML is operational it is explicitly labelled as explaining the deterministic comparison, not the ML model.
- Owner-scoped prediction-outcome drift and transparent manual retraining-readiness endpoints.
- Immutable operator outcome labels with SourceLine evidence. Automatic retraining and automatic promotion remain disabled.

### v5.4 multimodal planning

- Persistent connected road, rail, port, and sea legs with owner scope and immutable request snapshots.
- Per-leg ETA, cost source/completeness, risk source, compliance state, constraints, freshness, provenance, and lineage.
- Hard physical/compliance blocks override numerical score. Missing assessment becomes `MANUAL_REVIEW`; missing tariffs or risk remain `UNAVAILABLE`.
- Counted traceability rather than cosmetic provenance percentages.

### v6 integrated operations

- Owner-scoped operations overview across routes, schedules, shipments, events, compliance, predictions, multimodal plans, provider health, train sync, and traceability.
- Bounded application audit export.
- Shipment operational-state projection, explicitly not signalling/control or a physics twin.
- React `Nexus v6` console with integrated counts, SourceLine coverage, shipment states, and a working multimodal plan builder.
- Optional ixigo authorized-partner passenger-status adapter, manual schedule synchronization, opt-in worker, HTTPS/key gate, whitelisted fields, schedule ownership isolation, and SourceLine evidence.
- Schedule-specific provider observations carry an optional owner; global weather/space-weather observations remain shared. This prevents train-status leakage between users.
- Owner-scoped train-sync provenance links to reusable provider observations through explicit lineage. The worker processes every active schedule in stable 250-row pages rather than starving later schedules.
- Multimodal verified tariffs, non-operator risk, and asserted compliance statuses now require reference evidence or an owned ComplianceGuard check. Freshness is calculated server-side; missing risk/compliance forces review.

## Model evidence

Prepared dataset: 600 rows, 23 days, nine routes, three corridors, all `SIMULATED`, zero real/operator-confirmed rows.

The benchmark compared `HistGradientBoostingRegressor`, `RandomForestRegressor`, `ExtraTreesRegressor`, and `GradientBoostingRegressor`. Gradient Boosting won validation selection, was refit once on train+validation, and achieved test MAE `7.4394` minutes. The deterministic baseline achieved test MAE `4.3341` minutes; the ML candidate is therefore `71.65%` worse.

The result remains `CANDIDATE`. Promotion correctly failed `minimum_real_rows`, `no_synthetic_test_rows`, and `beats_deterministic_by_10_pct`. ClearPath Nexus continues using the deterministic ETA operationally while exposing the candidate only for advisory comparison. Repeated simulated retraining was deliberately stopped because it would optimize a synthetic generator rather than demonstrate real-world quality.

## API and schema

- API base remains `/api/v1`.
- FastAPI/OpenAPI product version is `6.0.0`.
- Alembic is forward through a single current head, including LiveOps/ML (`06`), predictive monitoring (`07`), multimodal (`08`), authorized train sync (`09`), provider-observation ownership (`10`), and multimodal evidence hardening (`11`).
- Supabase continues to issue client tokens; FastAPI verifies them and applies operational ownership authorization.
- No Supabase service-role credential is used by either client.

## Verification evidence

- Backend Ruff: passed.
- Backend pytest: `166 passed` after the final Bugbot hardening pass.
- Python compileall: passed.
- Python dependency integrity: `pip check` reported no broken requirements.
- OpenAPI export: version `6.0.0`, 55 paths, including multimodal, integrated operations, predictive drift/readiness, and train synchronization.
- Frontend frozen dependency install: passed.
- Frontend TypeScript: passed.
- Frontend ESLint: passed.
- Frontend production Vite build: passed; `IntegratedOperations` remains lazy-loaded at about 11 KB and the initial application chunk remains about 408 KB.
- Frontend production dependency audit: no known vulnerabilities.
- Live provider smoke: Open-Meteo parsed live/fresh data; NOAA current object-row schema parsed successfully and reported its real stale timestamp; RailRadar/AIS were skipped as unconfigured/auth-required.
- PostGIS 15 / PostGIS 3.4 and Redis 7: healthy; Redis PING/SET/GET/TTL passed.
- Real online migrations: base through current head applied against Docker PostGIS.
- API runtime smoke: `/health=ok`, `/ready=ready`, OpenAPI `6.0.0` with 55 paths, frontend HTTP `200` with the React root, and Redis `PONG`.
- High-confidence secret-material scan: no embedded token/private-key/service-role material found. One local `.env` exists for integration testing, is ignored, and is excluded from release archives.
- Android: Corretto 17.0.20.1, Android Platform 35, Build Tools 35, Gradle 8.9; clean/test/lint/assembleDebug passed. The test lifecycle is `NO-SOURCE` because the Android project currently has no unit tests. Lint reported 0 errors and 18 non-blocking warnings.
- Android APK: package `com.clearpath.nexus.debug`, version `6.0.0-device` (`versionCode 3`), 20,347,475 bytes, v2 signature verification passed, SHA-256 `AA7E59CE4E278410C25A593DFC9509C1C0B2C7E7ED840E5DC945EC45B80E8E8E`.
- Android release-artifact tasks fail closed without signing configuration or explicit CI-only unsigned opt-in; direct `packageRelease` bypass attempts were verified blocked.
- Bugbot reported 13 actionable findings (7 P1, 6 P2). All were corrected and covered by targeted/full verification before packaging.
- Browser QA confirmed the secure ClearPath Nexus sign-in screen rendered with email/password/sign-in controls and no console error/warning logs. Authenticated interior views were not visually inspected because no test user credential was bundled or invented.

## Product truth

- **IMPLEMENTED:** authentication verification/authorization, rail route evaluation/suggestion/history, clearance, deterministic reliability, scheduling/conflicts, dispatch, SourceLine, ComplianceGuard metadata checks, LiveOps/event lifecycle, shipment tracking, ML registry/fallback, predictive monitoring, operator-evidence multimodal evaluation, v6 operations overview/audit projection, web console.
- **LIVE WHEN REACHABLE:** Open-Meteo and NOAA SWPC.
- **OPTIONAL/AUTH REQUIRED:** OpenWeather, RailRadar, AISstream, maritime/rail feeds, ixigo authorized partner gateway.
- **SEEDED/DEMO:** segment engineering constraints, static congestion/historical delay, demo schedules, simulated model-development rows.
- **EXPERIMENTAL:** candidate ML inference, empirical confidence intervals when real calibration eventually exists, shipment operational-state projection.
- **FUTURE:** verified government/commercial integrations, automatic multimodal path discovery, verified tariffs/carbon, ERP/EDI connectors, certified engineering feeds, approved production retraining automation.

## Intentional limitations

- No public ixigo developer API was verified. The adapter does not scrape consumer endpoints and cannot be live-tested without a separately authorized HTTPS endpoint/key.
- Passenger train information is supplementary and cannot be treated as authoritative freight operations or railway control data.
- No model can honestly be called perfect. Current simulated evidence is insufficient for production ML, and the deterministic baseline is measurably better.
- OpenStreetMap geometry and seeded constraints do not certify bridge/OHE clearances, structure gauge, or axle load.
- ComplianceGuard is deterministic metadata decision support, not legal advice or government verification; it never invents fines.
- Multimodal plans currently evaluate supplied legs. They do not discover a verified factory-to-vessel route or tariff automatically.
