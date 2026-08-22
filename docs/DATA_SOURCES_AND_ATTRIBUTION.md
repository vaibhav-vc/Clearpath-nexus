# Data sources and attribution

Reviewed 22 August 2026. Provider terms can change; verify them before production or commercial deployment.

## OpenStreetMap

- Use: rail geometry, stations, and geographic context.
- License: Open Database License (ODbL).
- Attribution: `© OpenStreetMap contributors` with a link to <https://www.openstreetmap.org/copyright>.
- Limitation: geometry does not certify railway clearance, axle load, structure gauge, or operating authority.

## Open-Meteo

- Use: optional weather adapter.
- API data license: CC BY 4.0; see <https://open-meteo.com/en/license>.
- Terms: <https://open-meteo.com/en/terms>. The hosted free API has usage and non-commercial conditions and does not guarantee uninterrupted provision; review current terms for the intended deployment.
- Limitation: weather information is not railway operating authority.

## NOAA Space Weather Prediction Center

- Use: supplemental planetary Kp telemetry from <https://services.swpc.noaa.gov/products/>.
- Limitation: SourceLine records the feed as supplemental telemetry. ClearPath does not treat it as signalling or dispatch authority.

## RailRadar

- Use: optional third-party passenger-oriented rail signal when legitimate credentials and terms allow.
- Authority: supplementary and non-official for freight operations.
- Limitation: unconfigured or failed access is `UNAVAILABLE`, never fabricated.

## AISstream

- Use: optional AIS vessel-activity signal with legitimate configured access.
- Limitation: AIS activity is not a verified berth schedule and must never generate a fictional loading window.

## Operator input and seeded baselines

- Loading windows, shipment references, and document metadata are labelled `OPERATOR_INPUT`/operator-declared.
- Engineering limits, static congestion, and historical delay are labelled `SEEDED_BASELINE` where applicable.
