import type { TrainSyncState } from '../services/api'
import { isDegraded, resolveStatus } from '../types/status'
import { resolveRemediation } from '../lib/remediation'
import StatusBadge from './status/StatusBadge'
import DegradedStateCard from './status/DegradedStateCard'

/**
 * The ixigo supplementary sync strip.
 *
 * Previously inlined in ScheduleBoard, where `status` was painted amber
 * whatever it held -- so AUTH_REQUIRED and a healthy sync looked alike -- and
 * `last_error` was fetched but never shown.
 */
export default function TrainSyncPanel({ state }: { state: TrainSyncState }) {
  const status = resolveStatus(state.status)

  if (isDegraded(status)) {
    return (
      <DegradedStateCard
        className="mt-3"
        title="ixigo supplementary sync"
        state={state.status}
        message={state.last_error}
        hint={resolveRemediation(state.provider_key, state.status)}
        blastRadius={state.authority_notice}
      />
    )
  }

  return (
    <div className="mt-3 rounded-lg border border-cyan-800 bg-cyan-950/20 p-3 text-xs font-mono">
      <div className="flex items-center justify-between gap-2">
        <span className="text-cyan-300">ixigo supplementary sync</span>
        <div className="flex items-center gap-1.5">
          <StatusBadge value={state.status} />
          <StatusBadge value={state.freshness} domain="freshness" />
        </div>
      </div>
      <p className="mt-1 text-slate-400">
        {state.current_station ?? 'Position unavailable'} · delay{' '}
        {state.delay_minutes ?? 'UNAVAILABLE'} min
      </p>
      <p className="mt-2 text-[10px] text-slate-500">{state.authority_notice}</p>
    </div>
  )
}
