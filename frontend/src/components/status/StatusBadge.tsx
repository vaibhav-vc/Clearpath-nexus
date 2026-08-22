import { resolveStatus, type StatusDomain, type StatusTone } from '../../types/status'

export type StatusBadgeVariant = 'solid' | 'soft'

export interface StatusBadgeProps {
  value: string | null | undefined
  domain?: StatusDomain
  /** `solid` for dense control-room surfaces, `soft` for translucent panels. */
  variant?: StatusBadgeVariant
  /** Show the human label instead of the raw token. Operators expect the token. */
  showLabel?: boolean
  className?: string
}

// Static literals: Tailwind scans source text, so these can never be built by
// interpolation. `critical` is rose in both maps, which retires the stray red-*
// shades that used to appear only in ScheduleBoard.
const SOLID: Record<StatusTone, string> = {
  good: 'border-emerald-700 bg-emerald-950 text-emerald-300',
  info: 'border-cyan-700 bg-cyan-950 text-cyan-300',
  advisory: 'border-amber-700 bg-amber-950 text-amber-300',
  stale: 'border-orange-700 bg-orange-950 text-orange-300',
  critical: 'border-rose-700 bg-rose-950 text-rose-300',
  operator: 'border-violet-700 bg-violet-950 text-violet-300',
  simulated: 'border-fuchsia-700 bg-fuchsia-950 text-fuchsia-300',
  neutral: 'border-slate-700 bg-slate-900 text-slate-300',
  unknown: 'border-dashed border-slate-600 bg-slate-900 text-slate-400',
}

const SOFT: Record<StatusTone, string> = {
  good: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  info: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300',
  advisory: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  stale: 'border-orange-500/30 bg-orange-500/10 text-orange-300',
  critical: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
  operator: 'border-violet-500/30 bg-violet-500/10 text-violet-300',
  simulated: 'border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-300',
  neutral: 'border-slate-600/70 bg-slate-800/70 text-slate-400',
  unknown: 'border-dashed border-slate-600/70 bg-slate-800/70 text-slate-400',
}

export default function StatusBadge({
  value,
  domain = 'generic',
  variant = 'solid',
  showLabel = false,
  className = '',
}: StatusBadgeProps) {
  const status = resolveStatus(value, domain)
  const tones = variant === 'soft' ? SOFT : SOLID
  return (
    <span
      title={status.meaning ? `${status.label} — ${status.meaning}` : status.label}
      className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${tones[status.tone]} ${className}`}
    >
      {showLabel ? status.label : status.token}
    </span>
  )
}
