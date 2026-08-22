# Multimodal v5.4 and integrated operations v6

## What is implemented

`POST /api/v1/multimodal/plans` evaluates and persists an authenticated operator's connected road, rail, port, and sea legs. Every leg carries distance, ETA, cost state, risk state, compliance state, constraints, provider metadata, observation time, and freshness. The request is stored as an immutable snapshot.

The evaluator does not invent missing tariffs or risk. Cost is included in the total only when every leg has either a verified tariff or an operator-entered amount. Otherwise total cost is `UNAVAILABLE` and `cost_completeness` reports the real covered-leg fraction. Risk uses the highest supplied leg risk so a severe leg is not hidden by averaging.

`HARD_BLOCKED` constraints and blocked compliance override numerical risk and ETA. Unknown constraints or unassessed compliance produce `MANUAL_REVIEW`. These are decision-support recommendations, never dispatch authorization.

SourceLine stores three expected inputs per leg—base leg/ETA, cost, and risk—and a derived decision record. The response reports real `traced_inputs / expected_inputs`, unavailable counts, and lineage edges.

## Integrated operations

- `GET /api/v1/operations/overview` returns owned route, shipment, schedule, compliance, multimodal, prediction, train-sync, event, provider, and traceability counts.
- `GET /api/v1/operations/twin` returns the latest owned shipment state and position in one bounded query. It is labelled `OPERATIONAL_STATE_PROJECTION` and is not signalling, ATP, interlocking, dispatch control, or a physics twin.
- `GET /api/v1/operations/audit/export` returns a bounded owner-scoped JSON application-audit extract. It is not a government filing.

The React `Nexus v6` module exposes the overview, counted SourceLine coverage, shipment projection, and an operator-entered multimodal plan builder. Missing information stays visibly unavailable.

## Deliberate boundaries

Automatic road/sea route discovery, verified commercial tariff acquisition, carbon optimization, ERP/EDI connectors, and certified digital twins remain future integrations. Existing rail route evaluation and clearance are reused rather than duplicated.
