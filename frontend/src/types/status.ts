/**
 * The one place the frontend knows what a backend state string means.
 *
 * Before this module the vocabulary was scattered across three private badge
 * maps that each covered a different subset, so values the backend genuinely
 * emits -- AUTH_REQUIRED, CANDIDATE, PRODUCTION, OFFLINE -- fell through to a
 * neutral style and read as unremarkable. Everything resolves here instead.
 *
 * Mirrors, and must stay in step with:
 *   backend/app/services/provenance.py   CanonicalSourceType / FreshnessState /
 *                                        AvailabilityState
 *   backend/app/schemas/live_ops.py      LiveState (the only definition of
 *                                        AUTH_REQUIRED)
 *   backend/app/schemas/multimodal.py    SourceType / ComplianceState
 */

// ---------------------------------------------------------------------------
// Unions that mirror a backend Literal. Only use these where the backend field
// is itself a Literal -- several response fields are declared plain `str` and
// narrowing them here would be a type-level lie.
// ---------------------------------------------------------------------------

export type CanonicalSourceType =
  | 'LIVE_PROVIDER'
  | 'PUBLIC_OPEN_DATA'
  | 'CACHED_PROVIDER'
  | 'OPERATOR_INPUT'
  | 'SEEDED_BASELINE'
  | 'DERIVED'
  | 'SIMULATED'
  | 'OFFLINE_COMPUTED'
  | 'IMPORTED_DOCUMENT'
  | 'UNAVAILABLE'

/**
 * The multimodal request payload accepts a deliberate subset. Sending
 * OFFLINE_COMPUTED or IMPORTED_DOCUMENT is rejected with a 422, so outbound
 * payloads must use this narrower union rather than CanonicalSourceType.
 */
export type MultimodalSourceType = Exclude<
  CanonicalSourceType,
  'OFFLINE_COMPUTED' | 'IMPORTED_DOCUMENT'
>

export type CostSourceType = 'VERIFIED_TARIFF' | 'OPERATOR_INPUT' | 'UNAVAILABLE'

export type ComplianceState =
  | 'PASSED'
  | 'WARNING'
  | 'BLOCKED'
  | 'MANUAL_REVIEW'
  | 'NOT_ASSESSED'

// ---------------------------------------------------------------------------
// Presentation semantics
// ---------------------------------------------------------------------------

export type StatusTone =
  | 'good'
  | 'info'
  | 'advisory'
  | 'stale'
  | 'critical'
  | 'operator'
  | 'simulated'
  | 'neutral'
  | 'unknown'

/**
 * Some tokens mean different things on different axes -- circuit-breaker OPEN
 * means "provider is failing" while event-state OPEN means "needs attention".
 * Pass a domain wherever a collision is possible.
 */
export type StatusDomain =
  | 'generic'
  | 'freshness'
  | 'source'
  | 'availability'
  | 'severity'
  | 'eventState'
  | 'circuit'
  | 'conflict'
  | 'compliance'
  | 'model'
  | 'lifecycle'

export interface StatusDescriptor {
  /** Normalized token, or the trimmed raw value when unrecognized. */
  readonly token: string
  /** Human phrasing, e.g. 'Authorization required'. */
  readonly label: string
  readonly tone: StatusTone
  /** False when the value fell through to the typed fallback. */
  readonly known: boolean
  /** Truthful one-line explanation. Present for degraded states. */
  readonly meaning?: string
}

type StatusEntry = Omit<StatusDescriptor, 'token' | 'known'>

const STATUS_TABLE = {
  // Freshness -- provenance.py FreshnessState
  FRESH: { label: 'Fresh', tone: 'good' },
  AGING: { label: 'Aging', tone: 'advisory', meaning: 'The most recent value is past its preferred age but still usable.' },
  STALE: { label: 'Stale', tone: 'stale', meaning: 'The most recent value is too old to be treated as current.' },
  UNKNOWN: { label: 'Unknown', tone: 'unknown', meaning: 'No freshness could be established for this value.' },
  NOT_APPLICABLE: { label: 'Not applicable', tone: 'neutral' },

  // Live provider state -- live_ops.py LiveState
  LIVE: { label: 'Live', tone: 'good' },
  CACHED: { label: 'Cached', tone: 'info', meaning: 'Served from the last good cached value, not a fresh provider call.' },
  RATE_LIMITED: { label: 'Rate limited', tone: 'advisory', meaning: 'The provider quota is exhausted, so no new value was retrieved.' },
  AUTH_REQUIRED: {
    label: 'Authorization required',
    tone: 'advisory',
    meaning: 'The provider requires authorized access that is not configured, so no value was retrieved.',
  },
  INVALID: { label: 'Invalid', tone: 'critical', meaning: 'The provider replied, but the payload failed validation and was rejected.' },

  // Canonical source types -- provenance.py CanonicalSourceType
  LIVE_PROVIDER: { label: 'Live provider', tone: 'good' },
  PUBLIC_OPEN_DATA: { label: 'Public open data', tone: 'good' },
  CACHED_PROVIDER: { label: 'Cached provider', tone: 'info' },
  OPERATOR_INPUT: { label: 'Operator input', tone: 'operator', meaning: 'Supplied by an operator rather than measured by a provider.' },
  SEEDED_BASELINE: { label: 'Seeded baseline', tone: 'neutral', meaning: 'A seeded demonstration baseline, not an observed measurement.' },
  DERIVED: { label: 'Derived', tone: 'info' },
  SIMULATED: { label: 'Simulated', tone: 'simulated', meaning: 'Generated for pipeline validation. Never eligible for production decisions.' },
  OFFLINE_COMPUTED: { label: 'Offline computed', tone: 'neutral', meaning: 'Computed on-device without backend intelligence.' },
  IMPORTED_DOCUMENT: { label: 'Imported document', tone: 'neutral' },
  UNAVAILABLE: { label: 'Unavailable', tone: 'critical', meaning: 'No value is available and none has been substituted.' },

  // Availability -- provenance.py AvailabilityState
  AVAILABLE: { label: 'Available', tone: 'good' },
  DEGRADED: { label: 'Degraded', tone: 'advisory' },
  NOT_CONFIGURED: {
    label: 'Not configured',
    tone: 'neutral',
    meaning: 'This layer has no credentials configured, so it is switched off rather than estimated.',
  },

  // Severity
  INFO: { label: 'Info', tone: 'info' },
  LOW: { label: 'Low', tone: 'neutral' },
  MEDIUM: { label: 'Medium', tone: 'advisory' },
  HIGH: { label: 'High', tone: 'stale' },
  CRITICAL: { label: 'Critical', tone: 'critical' },

  // Event lifecycle
  ACKNOWLEDGED: { label: 'Acknowledged', tone: 'info' },
  RESOLVED: { label: 'Resolved', tone: 'good' },
  DISMISSED: { label: 'Dismissed', tone: 'neutral' },

  // Schedule conflict
  CLEAR: { label: 'Clear', tone: 'good' },
  WARNING: { label: 'Warning', tone: 'advisory' },
  BLOCKED: { label: 'Blocked', tone: 'critical' },
  HARD_BLOCKED: { label: 'Hard blocked', tone: 'critical', meaning: 'A physical clearance check failed. This overrides any numerical score.' },

  // Compliance
  PASSED: { label: 'Passed', tone: 'good' },
  MANUAL_REVIEW: { label: 'Manual review', tone: 'advisory' },
  NOT_ASSESSED: { label: 'Not assessed', tone: 'unknown', meaning: 'No compliance assessment has been run for this item.' },

  // Multimodal plan status and recommendation
  EVALUATED: { label: 'Evaluated', tone: 'good' },
  REVIEW_REQUIRED: { label: 'Review required', tone: 'advisory' },
  PROCEED: { label: 'Proceed', tone: 'good' },
  PROCEED_WITH_REVIEW: { label: 'Proceed with review', tone: 'advisory' },
  HOLD: { label: 'Hold', tone: 'critical' },

  // Model lifecycle
  PRODUCTION: { label: 'Production', tone: 'good' },
  CANDIDATE: {
    label: 'Candidate',
    tone: 'advisory',
    meaning: 'Advisory only. Deterministic prediction stays in control until every promotion gate passes.',
  },

  // Shipment and schedule lifecycle
  PLANNED: { label: 'Planned', tone: 'neutral' },
  READY: { label: 'Ready', tone: 'good' },
  DISPATCHED: { label: 'Dispatched', tone: 'info' },
  IN_TRANSIT: { label: 'In transit', tone: 'info' },
  CANCELLED: { label: 'Cancelled', tone: 'neutral' },

  // Frontend-synthesized
  OFFLINE: { label: 'Offline', tone: 'neutral', meaning: 'Tracking is stopped for this shipment, so no position is being collected.' },
  TRACED: { label: 'Traced', tone: 'good' },
} as const satisfies Record<string, StatusEntry>

export type KnownStatusToken = keyof typeof STATUS_TABLE

/**
 * Circuit-breaker OPEN/CLOSED invert the usual reading: an open breaker means
 * the provider is failing. Without this, badging circuit_state would paint a
 * failing provider the same as an event awaiting attention.
 */
const DOMAIN_OVERRIDES: Partial<Record<StatusDomain, Readonly<Record<string, StatusEntry>>>> = {
  circuit: {
    OPEN: { label: 'Open', tone: 'critical', meaning: 'The breaker is open: repeated failures have suspended calls to this provider.' },
    HALF_OPEN: { label: 'Half open', tone: 'advisory', meaning: 'The breaker is trialling a single call before restoring traffic.' },
    CLOSED: { label: 'Closed', tone: 'good' },
  },
  eventState: {
    OPEN: { label: 'Open', tone: 'advisory' },
  },
}

const UNKNOWN_ENTRY: StatusEntry = {
  label: 'Unrecognized state',
  tone: 'unknown',
  meaning: 'This value is not in the known state vocabulary and has not been interpreted.',
}

export function normalizeStatusToken(value: string): string {
  return value.trim().toUpperCase().replace(/[\s-]+/g, '_')
}

/**
 * Resolve any backend state string. Accepts `string` rather than a union
 * because several backend response fields are declared plain `str`; an
 * unrecognized value resolves to an explicit `unknown` descriptor and is never
 * silently presented as healthy.
 */
export function resolveStatus(
  value: string | null | undefined,
  domain: StatusDomain = 'generic',
): StatusDescriptor {
  const raw = (value ?? '').trim()
  if (!raw) {
    return { token: 'UNSPECIFIED', ...UNKNOWN_ENTRY, known: false }
  }
  const token = normalizeStatusToken(raw)

  const overrides = DOMAIN_OVERRIDES[domain]
  if (overrides && Object.hasOwn(overrides, token)) {
    return { token, ...overrides[token], known: true }
  }
  if (Object.hasOwn(STATUS_TABLE, token)) {
    return { token, ...STATUS_TABLE[token as KnownStatusToken], known: true }
  }
  return { token: raw, ...UNKNOWN_ENTRY, known: false }
}

/** True when a state warrants explaining itself rather than passing quietly. */
export function isDegraded(descriptor: StatusDescriptor): boolean {
  return (
    !descriptor.known ||
    descriptor.tone === 'advisory' ||
    descriptor.tone === 'stale' ||
    descriptor.tone === 'critical' ||
    descriptor.tone === 'unknown'
  )
}
