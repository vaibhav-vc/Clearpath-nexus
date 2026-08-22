# Nexus ComplianceGuard

ComplianceGuard is a pre-dispatch legal and regulatory decision-support module. It is not a lawyer, government service, customs authority, or declaration of compliance.

## Implemented MVP rule pack

- Stored route physical-clearance state.
- Presence of operator-declared permit, insurance, and cargo-declaration metadata.
- Document expiry at check time.
- Permit/document expiry before estimated route completion.
- Document verification state.
- Cargo-declaration completeness confirmation.
- Human-approval confirmation.
- Transporter, shipment, E-Way Bill, and port/customs reference metadata gaps.

Uncertainty produces `MANUAL_REVIEW`. A physical route failure produces `BLOCKED`. A time-bound expiry issue produces `WARNING` unless a higher-priority state applies. Penalty text is deliberately non-numeric unless a verified authoritative tariff is later added.

## API

- `POST /api/v1/compliance/routes/{route_id}/checks`
- `GET /api/v1/compliance/routes/{route_id}/checks`
- `GET /api/v1/compliance/checks/{check_id}`
- `POST /api/v1/compliance/checks/{check_id}/override`

All records are owner-scoped. Documents are tied to the exact historical check. Overrides do not change the underlying findings; every override appends a user, reason, and timestamp event while the check retains a latest-event compatibility summary. Check history is bounded by pagination and assembled with batched queries.

A required document counts as present only when it has an identifying document number, checksum, or storage reference. A type-only placeholder does not satisfy the rule.

## Current limitations

- No government authentication bypass or automatic government verification.
- No legal scraping or invented laws.
- No verified penalty schedules.
- The seeded rule source is an internal evidence policy, explicitly marked non-official and operator-defined.
