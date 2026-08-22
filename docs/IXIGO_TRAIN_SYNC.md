# Optional ixigo train synchronization

## Access boundary

As of 22 August 2026, ixigo's official consumer pages advertise live passenger train status and its corporate disclosures describe ixigo's own API-based IRCTC access, but no public developer API or reusable public partner contract was verified. ClearPath Nexus therefore does not call or scrape ixigo's consumer endpoints.

The adapter is enabled only when an operator has separately authorized access and configures:

- `IXIGO_SYNC_ENABLED=true`
- `IXIGO_TRAIN_STATUS_URL=https://...`
- `IXIGO_API_KEY=...`
- optional `IXIGO_SYNC_INTERVAL_SECONDS`

The URL must be HTTPS. Without all required configuration, the adapter returns `AUTH_REQUIRED` and does not make a network request. Secrets are sent only in the backend `x-api-key` header and are never returned, logged, persisted, or exposed to the web/Android clients.

## Normalized contract

The authorized gateway must return a JSON object, optionally under `data`, with an observation timestamp in `observed_at`, `updated_at`, or `last_updated`. The adapter whitelists only:

- train number;
- running status;
- current station/code;
- delay minutes;
- latitude/longitude;
- scheduled/estimated arrival.

Unexpected passenger, booking, PNR, credential, or key fields are discarded. Timestamps and numeric ranges are validated before persistence.

## Synchronization behavior

- `POST /api/v1/live/train-sync/schedules/{schedule_id}` performs an owner-scoped manual sync.
- `GET /api/v1/live/train-sync/schedules/{schedule_id}` reads the latest owned state.
- `python -m app.workers.train_synchronizer` synchronizes active schedules with bounded concurrency.
- Docker keeps the worker in the opt-in `ixigo` profile so an unconfigured integration is not treated as core runtime.

Provider observations, freshness, failures, and schedule associations are stored in SourceLine. The signal is always labelled supplementary passenger information. It is not freight railway authority, signalling, Kavach/ATP, interlocking, train control, or official dispatch.

Official references reviewed: [ixigo trains](https://www.ixigo.com/trains), [ixigo terms of use](https://www.ixigo.com/about/terms-of-use/), and [ixigo corporate prospectus](https://rocket.ixigo.com/legal/Prospectus.pdf).
