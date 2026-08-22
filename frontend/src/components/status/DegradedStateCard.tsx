import { resolveStatus, type StatusDomain } from '../../types/status'
import type { RemediationHint } from '../../lib/remediation'
import StatusBadge, { type StatusBadgeVariant } from './StatusBadge'

export interface DegradedStateCardProps {
  title: string
  /** The backend state, e.g. AUTH_REQUIRED, NOT_CONFIGURED, CANDIDATE. */
  state: string
  domain?: StatusDomain
  /** Server-supplied explanation. Always wins over our own wording. */
  message?: string | null
  /** What the operator can do about it. Deployment advice, not evidence. */
  hint?: RemediationHint
  /** Overrides `hint.blastRadius` when the server supplies its own notice. */
  blastRadius?: string
  variant?: StatusBadgeVariant
  className?: string
}

/**
 * One presentation for every "this is switched off / not trusted yet" state.
 *
 * The message precedence encodes who owns what: the backend owns the
 * diagnosis, so its own words are shown whenever it supplies them, and our
 * vocabulary only fills a gap it left.
 */
export default function DegradedStateCard({
  title,
  state,
  domain = 'generic',
  message,
  hint,
  blastRadius,
  variant = 'solid',
  className = '',
}: DegradedStateCardProps) {
  const status = resolveStatus(state, domain)
  const explanation =
    message?.trim() || status.meaning || 'No explanation was supplied by the provider.'
  const reassurance = blastRadius ?? hint?.blastRadius

  return (
    <div className={`rounded-xl border border-slate-700/70 bg-slate-950/80 p-5 ${className}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-600 bg-slate-900">
          <span className="h-2 w-2 rounded-full bg-slate-500" />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
            <StatusBadge value={state} domain={domain} variant={variant} />
          </div>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">{explanation}</p>
          {hint ? (
            <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
              {hint.envVar ? (
                <>
                  Set{' '}
                  <code className="rounded bg-slate-800/80 px-1 py-0.5 font-mono text-cyan-400">
                    {hint.envVar}
                  </code>{' '}
                </>
              ) : null}
              {hint.text}
            </p>
          ) : null}
          {reassurance ? (
            <p className="mt-2 text-[11px] leading-relaxed text-slate-600">{reassurance}</p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
