import { useState } from 'react'
import { fetchRouteEvidence } from '../services/api'
import type { ProvenanceSummary, RouteEvidence } from '../types/route'

export default function DataTrustCard({ routeId, summary }: { routeId: string; summary: ProvenanceSummary }) {
  const [evidence, setEvidence] = useState<RouteEvidence | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const inspect = async () => {
    setOpen(true)
    if (evidence) return
    try {
      setEvidence(await fetchRouteEvidence(routeId))
    } catch {
      setError('Stored evidence could not be loaded.')
    }
  }

  return (
    <>
      <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-cyan-300">Nexus SourceLine</p>
            <p className="mt-1 text-sm font-semibold text-white">
              Traceability: {summary.traceability.traced} / {summary.traceability.total} decision inputs
            </p>
            <p className="text-[11px] text-slate-400">
              {summary.traceability.coverage_pct}% traced from stored evidence
            </p>
          </div>
          <button onClick={() => void inspect()} className="rounded-lg bg-cyan-500 px-3 py-2 text-xs font-bold text-slate-950">
            Inspect evidence
          </button>
        </div>
        {summary.warnings[0] ? <p className="mt-3 text-[11px] text-amber-300">{summary.warnings[0]}</p> : null}
      </div>

      {open ? (
        <div className="fixed inset-0 z-[1000] flex justify-end bg-slate-950/75" onClick={() => setOpen(false)}>
          <section className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-700 bg-slate-950 p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white">Decision evidence</h2>
                <p className="text-xs text-slate-400">Immutable snapshot for route {routeId.slice(0, 8)}</p>
              </div>
              <button onClick={() => setOpen(false)} className="text-sm text-slate-400 hover:text-white">Close</button>
            </div>
            {error ? <p className="mt-6 text-sm text-rose-300">{error}</p> : null}
            {!evidence && !error ? <p className="mt-6 text-sm text-slate-400">Loading stored evidence…</p> : null}
            {evidence ? (
              <div className="mt-5 space-y-4">
                {evidence.components.map((component) => (
                  <article key={component.role} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="font-semibold text-slate-100">{component.label}</h3>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${component.status === 'TRACED' ? 'bg-emerald-950 text-emerald-300' : 'bg-amber-950 text-amber-300'}`}>
                        {component.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{component.explanation}</p>
                    <div className="mt-3 space-y-2">
                      {evidence.records.filter((record) => component.record_ids.includes(record.id)).map((record) => (
                        <div key={record.id} className="rounded-lg bg-slate-950 p-3 text-xs">
                          <div className="flex flex-wrap justify-between gap-2">
                            <span className="font-mono text-cyan-300">{record.entity_type}</span>
                            <span className="text-slate-400">{record.canonical_source_type} · {record.freshness.state}</span>
                          </div>
                          <p className="mt-1 text-slate-400">Source: {record.source?.label ?? 'Stored derived record'}</p>
                          {record.excluded_reason ? <p className="mt-1 text-amber-300">Excluded: {record.excluded_reason}</p> : null}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
                {evidence.warnings.map((warning) => <p key={warning} className="rounded-lg border border-amber-800/50 bg-amber-950/20 p-3 text-xs text-amber-200">{warning}</p>)}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </>
  )
}
