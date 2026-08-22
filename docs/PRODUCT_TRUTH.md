# Product truth — 22 August 2026

This file describes the repository, not planned marketing claims.

## Implemented

- Supabase token issuance with FastAPI verification and operational authorization.
- Owner-scoped route history, schedules, dispatch, SourceLine evidence, compliance checks, documents, and overrides.
- Deterministic routing, cargo clearance, reliability, weather risk, congestion blending, port-window alignment, scheduling/conflict detection, predictive delay, analytics, and simulations.
- Source catalog, persisted route decision snapshots, provenance records, lineage edges, real `traced / total` calculations, source-mode/freshness counts, checksums, algorithm versions, applied weights, and exclusions.
- Historical evidence retrieval from stored snapshots without provider refetch.
- Compliance metadata review for required documents, expiry, permit-versus-ETA, cargo declaration, human approval, and reference gaps.
- Immutable per-check document association and append-only compliance override events.
- Paginated compliance history with batched item/source/document/event loading.
- Web SourceLine and ComplianceGuard interfaces.
- Android SourceLine summary parsing and explicit `OFFLINE_COMPUTED` fallback semantics.
- Normalized Open-Meteo and NOAA envelopes with timestamp/range validation, bounded retry, circuit breaking, durable observation storage, Redis latest-value caching, and a single live-ingestor process.
- Persisted operational event lifecycle with provider/weather events, authenticated SSE, acknowledgement/resolution, and observation/SourceLine references.
- Owner-scoped shipment registration and explicit, stoppable position sharing with `OPERATOR_INPUT` or `SIMULATED` provenance.
- LiveOps web control center for events, provider health, observation freshness, tracked shipments, and model state.
- Delay-model dataset/training/model/prediction registries, deterministic benchmarking, chronological split, leakage controls, checksummed artifacts, inference fallback, and outcome labeling.
- Empirical delay intervals gated on at least 30 real held-out labels, exact deterministic feature-contribution explanations, owner-scoped outcome drift monitoring, and manual-only retraining readiness gates.
- Persistent road/rail/port/sea multimodal plans with connected-leg validation, operator/verified/unavailable cost states, sourced risk, compliance/hard constraints, immutable snapshots, counted traceability, and SourceLine lineage.
- Owner-scoped v6 integrated-operations overview, application audit extract, and shipment state projection across the existing planning/live/tracking/predictive/compliance/scheduling modules.
- Optional authorized ixigo-partner passenger train status synchronization, fail-closed configuration, normalized/whitelisted fields, schedule ownership isolation, SourceLine records, and an opt-in background worker.

## Partial

- Some external adapters are live only when configured and reachable. Provider absence remains explicit.
- ComplianceGuard evaluates operator-declared metadata and an internal rule pack. It does not validate documents against government systems.
- Android displays the SourceLine summary but does not yet include the web evidence graph or compliance workflow.
- Provider health is process-local observational telemetry, not a contractual SLA monitor.
- Route weather is sampled along each evaluated corridor, but the separate ingestor currently monitors four configured reference points rather than dynamically subscribing to every active route.
- Candidate ML predictions are advisory. Until real-data gates pass, deterministic delay remains the operational value.
- Confidence intervals remain unavailable when calibration is simulated, undersized, or absent; they are not guarantees even when available.
- Multimodal legs are operator/provider supplied. The repository does not yet discover end-to-end road/sea paths or verified commercial tariffs automatically.
- The shipment “twin” is an operational state projection, not a physics model, signalling replica, or control system.
- The ixigo adapter cannot be live-tested without separately authorized partner documentation, endpoint, and credentials. No public developer API was verified and no consumer endpoint is scraped.

## Optional integrations

- OpenWeather requires an API key.
- RailRadar and AISstream require legitimate configured access. They are supplementary and non-authoritative.
- ixigo synchronization requires a separately authorized HTTPS partner gateway and key. It is passenger-oriented and supplementary, not official freight control.
- Operator-entered port loading windows are the reliable MVP path when no verified berth feed exists.

## Seeded/demo

- Segment clearance and capacity constraints.
- Static congestion and historical-delay baselines.
- Demo schedules and some simulator scenarios.

Seeded values are labelled in SourceLine and must not be treated as certified railway engineering data.

## Future

- Verified government compliance integrations, curated jurisdiction-specific legal rule packs, document file storage/scanning, advanced event-to-alternative-route automation, verified tariff/carbon optimization, automatic multimodal path discovery, and enterprise ERP/EDI connectors.
- Automatic/continuous retraining, congestion forecasting, and route-specific models remain future work.
- These are not represented as current capabilities.
