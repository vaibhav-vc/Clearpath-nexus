# Live Data Integration Plan — Demo Corridor Only

> **ARCHIVED PROVIDER RESEARCH.** Free tiers, quotas, terms, and provider availability can change. This file is not a current entitlement claim. Review `docs/DATA_SOURCES_AND_ATTRIBUTION.md` and each provider's current official terms before use.

Corridor: **NGP → BSL → MMR → KYN → JNPT** (+ PUNE branch), Maharashtra.

## Research outcome — what is actually free

| Need | Source | Free tier | Verdict |
|---|---|---|---|
| Live train delays | **RailRadar** `api.railradar.in/v1` | 1,000 req/month sandbox, no card | **USE** |
| Port vessel activity | **aisstream.io** `wss://stream.aisstream.io/v0/stream` | Free, unlimited, API key | **USE** |
| Track geometry | Overpass / OSM | Free | already in use |
| Weather | OpenWeatherMap | Free tier | already in use |
| Berth *schedules* | — | none exist free | **operator input** |

Rejected: indianrailapi.com (key required, thin free tier), erail (unofficial),
RapidAPI IRCTC mirrors (20 calls/month), MarineTraffic / VesselFinder / Datalastic (paid).

## Critical constraint discovered

AIS tells us **congestion**, not **schedule**.

AIS broadcasts where ships are and whether they are anchored or moored. It does
NOT broadcast the vessel loading window. So:

- `congestion_score` → can go live (AIS + RailRadar)
- `port_sync` window alignment → still needs operator input

Do not conflate these. Claiming live berth scheduling from AIS would be the same
class of bug we just removed from `port_sync.py`.

Also: **aisstream blocks browser/CORS connections by design** and is explicitly
BETA with no SLA. It must be consumed server-side, and must degrade cleanly.

## Budget: 1,000 req/month

5 corridor stations polled every 30 min = 7,200/month. Too many.

Poll every 2 hours, cache 2h TTL: 5 × 12/day × 30 = **1,800/month**. Still over.
Poll on demand with a 2h cache, corridor-wide single refresh: worst case
5 req per refresh, ~150 refreshes/month available. **Cache is mandatory, not
an optimisation.**

## Design rules (inherited from the port_sync fix)

1. Never fabricate. Every reading carries `source` + `fetched_at`.
2. Unavailable ≠ zero. Missing live data falls back to the seeded static value
   and says so.
3. Live data *adjusts* the static baseline; it does not replace the model.
4. Rate limit is a first-class concern; exhaustion is a normal state, not an error.

## Steps

1. `services/live_rail.py` — RailRadar client, corridor congestion from live boards
2. `services/live_port.py` — AIS collector, JNPT anchorage/berth occupancy
3. Config + requirements
4. Fixture tests (no network in sandbox — parsing verified against recorded payloads)
5. Wire into `router_engine.compute_congestion_score`

## Verification limits

The sandbox has **no outbound network**. I can verify parsing, scoring, cache,
and failure handling against recorded fixtures. Live connectivity must be
confirmed by the developer with real keys.
