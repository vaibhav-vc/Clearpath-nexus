# Nexus LiveOps

LiveOps is the v5.2 live-data and operational-event layer. It does not turn ClearPath Nexus into signalling, interlocking, official dispatch control, or autonomous train control.

## Architecture

`python -m app.workers.live_ingestor` is the single polling process in the existing backend codebase. It fetches configured providers, validates and normalizes responses, persists observations and SourceLine records, updates Redis latest-value keys, updates provider runtime state, and generates deterministic events. API workers do not start their own polling loops.

Current monitored weather points are NGP, BSL, KYN, and JNPT. Route evaluation separately samples three points for corridors below 500 km and up to five for longer routes; calls share the existing rounded-location Redis cache.

## Live envelope

Every normalized observation exposes provider identity/version, category, canonical source type, raw provider state, observed/fetched timestamps, age, freshness, cache state, validation quality, optional coordinates, request ID, attribution, and limitations.

Normalized operational states are `LIVE`, `CACHED`, `AGING`, `STALE`, `UNAVAILABLE`, `RATE_LIMITED`, `AUTH_REQUIRED`, `INVALID`, `OPERATOR_INPUT`, `SIMULATED`, and `OFFLINE_COMPUTED`.

Validation rejects future timestamps, invalid coordinates, non-finite numeric values, and missing provider-required fields. Retries are bounded with exponential backoff and jitter. Three consecutive failures open the circuit for a configurable cooldown; no provider retry is infinite.

## Persistence and retention

- `provider_observations` stores normalized, checksummed observations and their SourceLine record.
- `provider_runtime_state` stores success/failure time, circuit state, latency, freshness, rate-limit state, and authentication state.
- `operational_events` stores event type, severity, lifecycle, timestamps, affected route/shipment, and source observation/provenance references.
- `shipments` and `shipment_positions` provide owner-scoped, opt-in tracking.

Duplicate provider payloads are suppressed using provider, timestamp, location, state, and normalized data—not fetch-attempt identity. Raw operational observations default to 30 days retention and high-frequency positions to 14 days. Decision snapshots and compliance evidence follow their longer existing retention policy.

## Event engine

Implemented automatic events are `HEAVY_RAIN`, `LOW_VISIBILITY`, `HIGH_WIND`, `PROVIDER_STALE`, and `PROVIDER_UNAVAILABLE`. The schema supports `INFO`, `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`; ordinary provider outages are `MEDIUM`, not `CRITICAL`.

States are `OPEN`, `ACKNOWLEDGED`, `RESOLVED`, and `DISMISSED`. Humans remain responsible for route changes. Events never silently reroute or dispatch freight.

## API

- `GET /api/v1/live/observations`
- `GET /api/v1/live/provider-health`
- `GET /api/v1/live/events`
- `GET /api/v1/live/events/stream` (authenticated SSE)
- `PATCH /api/v1/live/events/{event_id}`
- `POST /api/v1/live/shipments`
- `PATCH /api/v1/live/shipments/{shipment_id}/tracking?enabled=true|false`
- `POST /api/v1/live/shipments/{shipment_id}/positions`
- `GET /api/v1/live/shipments`

The web UI polls the bounded event endpoint every 15 seconds so Supabase bearer authentication remains explicit. The SSE endpoint is available for clients that can attach the bearer token safely.
