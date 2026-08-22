import { normalizeStatusToken } from '../types/status'

/**
 * What an operator can do about a switched-off layer.
 *
 * Deliberately client-side. The backend owns the diagnosis -- why a layer is
 * unavailable -- and already supplies it. This is deployment instruction: it
 * has no provenance, is not evidence, and naming backend environment variables
 * in an API response would disclose config topology for no benefit.
 */
export interface RemediationHint {
  /** Backend environment variable to set, rendered as inline code. */
  readonly envVar?: string
  readonly text: string
  /** What keeps working regardless. */
  readonly blastRadius: string
}

const REMEDIATION: Readonly<Record<string, Readonly<Record<string, RemediationHint>>>> = {
  // LiveCorridorTrafficResponse.provider -- services/railradar.py
  railradar: {
    NOT_CONFIGURED: {
      envVar: 'RAILRADAR_API_KEY',
      text: 'in the backend environment to enable this layer with a free RailRadar sandbox key, then restart the backend.',
      blastRadius:
        'Routing, clearance, and scheduling are unaffected — this layer is a supplementary overlay, and no traffic is estimated while it is off.',
    },
    AUTH_REQUIRED: {
      envVar: 'RAILRADAR_API_KEY',
      text: 'is set but RailRadar rejected it. Check the key for typos or expiry, then restart the backend.',
      blastRadius:
        'Routing, clearance, and scheduling are unaffected. No traffic is estimated while the key is rejected.',
    },
    RATE_LIMITED: {
      text: 'The RailRadar request quota is exhausted. It resets on the provider billing cycle.',
      blastRadius:
        'Routing, clearance, and scheduling are unaffected. Cached corridor results keep serving until they expire.',
    },
  },
  // TrainSyncState.provider_key -- services/ixigo_sync.py
  ixigo_partner: {
    AUTH_REQUIRED: {
      envVar: 'IXIGO_SYNC_ENABLED',
      text: 'along with IXIGO_TRAIN_STATUS_URL and IXIGO_API_KEY, and only with separately authorized partner access.',
      blastRadius:
        'Route planning and scheduling continue normally. This layer is supplementary passenger information, never freight authority or train control.',
    },
  },
  // Synthetic key for the model registry, which has no provider field.
  delay_model: {
    CANDIDATE: {
      text: 'Promotion requires every gate to pass on real operational rows — rebuild the dataset without --include-simulated, retrain, then evaluate.',
      blastRadius:
        'Deterministic ETA remains in control and is unaffected. No candidate model influences an operational decision.',
    },
  },
}

export function resolveRemediation(
  providerKey: string | null | undefined,
  state: string | null | undefined,
): RemediationHint | undefined {
  const provider = (providerKey ?? '').trim().toLowerCase()
  const token = normalizeStatusToken(state ?? '')
  if (!provider || !token) return undefined
  if (!Object.hasOwn(REMEDIATION, provider)) return undefined
  const byState = REMEDIATION[provider]
  return Object.hasOwn(byState, token) ? byState[token] : undefined
}
