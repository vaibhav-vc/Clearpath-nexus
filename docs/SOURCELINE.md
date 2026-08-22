# Nexus SourceLine

SourceLine answers: where did an input come from, how old was it, how was it transformed, was it used or excluded, and how did it affect the stored decision?

## Persistence model

- `data_sources` stores provider identity, authority, reference, license/attribution, limitations, and freshness policy.
- `route_decision_snapshots` freezes cargo, route segments, clearance state, RRI, inputs, weights, exclusions, alerts, and algorithm versions.
- `provenance_records` stores raw and derived evidence with timestamps, freshness, availability, checksum, decision role, transformation, and safe value summary.
- `lineage_edges` connects inputs using `INPUT_TO`, `DERIVED_FROM`, `OVERRIDES`, `EXCLUDED_FROM`, `VALIDATES`, `REFERENCES`, or `FALLBACK_FOR`.
- `provider_observations` persists normalized live envelopes and points back to their SourceLine record.
- ML feature vectors and delay predictions are persisted as derived records linked by `TRANSFORMED_INTO`; model name, version, status, feature schema, artifact checksum, features, fallback reason, and operational-use state remain inspectable.

The route and its evidence are committed in one database transaction. Historical evidence endpoints only query these records; they never fetch current weather to explain a past decision.

## Traceability calculation

The route decision denominator is five major roles: clearance decision, weather, port alignment, congestion, and historical delay.

Coverage is `traced roles / 5`. An explicit unavailable record can be traced because the absence and its decision treatment are evidence. The application does not show an arbitrary provenance-completeness percentage.

## API

- `GET /api/v1/provenance/routes/{route_id}` — owner-scoped stored evidence and lineage.
- `GET /api/v1/provenance/records/{record_id}` — owner-scoped parent/child neighborhood.
- `GET /api/v1/provenance/sources` — authenticated source catalog.
- `GET /api/v1/provenance/health` — authenticated process-local provider observations.

Route evaluate/suggest responses also include a compact `provenance_summary`.

## Safety

- Secret-like metadata keys are redacted before persistence.
- Weather fallbacks and unavailable providers are explicit.
- Seeded engineering/static inputs carry warnings.
- Physical clearance is represented by an `OVERRIDES` edge when it forces the final RRI to zero.
- Cached RailRadar and stale AIS evidence retain their actual source state and observation timestamp.
- Port evidence stores evaluation time, train-arrival offset, calculated arrival, loading-window bounds, berth metadata, and vessel state for reproduction.
- Evidence components include upstream raw-provider ancestors, including explicitly excluded inputs.
