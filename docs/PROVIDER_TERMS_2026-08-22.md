# Provider access and terms check — 22 August 2026

This is implementation guidance, not legal advice. Re-check terms before commercial deployment.

## Open-Meteo

- Official documentation: https://open-meteo.com/en/docs
- Terms reviewed: https://open-meteo.com/en/terms
- Current free hosted API terms state non-commercial use, rate ceilings, and CC BY 4.0 data licensing. A commercial ClearPath deployment must use a suitable commercial plan or a legitimately self-hosted/provider-approved alternative.
- v5.2 uses bounded, minutes-scale requests with attribution and does not imply an SLA.

## NOAA SWPC

- Product endpoint: https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
- Federal disclaimer: https://www.weather.gov/disclaimer
- v5.2 uses the planetary K-index only as supplemental environmental telemetry. It is never represented as railway signalling or dispatch authority.

## RailRadar

- Provider site and developer entry point: https://railradar.in/
- The provider currently advertises a 1,000-request/month developer sandbox. Access is key-gated and supplementary; its passenger/crowdsourced telemetry is not official freight-control data.
- v5.2 retains explicit optional configuration and budget-aware caching. No credential was bundled.

## AISstream

- Official documentation: https://aisstream.io/documentation
- Access requires an authenticated API key and a backend WebSocket. The documentation explicitly warns against exposing keys in browser code and describes key/user throttling.
- ClearPath keeps the key server-side. AIS is vessel-activity evidence only; it is not a verified berth-loading schedule.

## ixigo

- Official train consumer page: https://www.ixigo.com/trains
- Official user agreement: https://www.ixigo.com/about/terms-of-use/
- Corporate prospectus: https://rocket.ixigo.com/legal/Prospectus.pdf
- ixigo advertises passenger live-running status and discloses its own IRCTC API access, but this review did not identify a public developer API or reusable public partner contract.
- ClearPath does not scrape ixigo consumer/private endpoints. Its adapter remains `AUTH_REQUIRED` unless a customer supplies a separately authorized HTTPS partner endpoint and server-side key.
- Any returned signal is supplementary passenger information, never official freight control, signalling, or dispatch authority.

## Operator and legal sources

Port/loading windows remain `OPERATOR_INPUT`, `AUTHORIZED_FEED`, `IMPORTED_SCHEDULE`, or `UNAVAILABLE`. Compliance rule metadata remains curated/versioned and is never automatically overwritten from uncontrolled scraping.
