import { useEffect, useMemo, useState } from 'react'
import { fetchRouteEvidence, fetchRouteHistory } from '../services/api'
import type { RouteEvidence, RouteHistoryItem } from '../types/route'

export default function RouteHistoryPanel({
  onSelectRoute,
}: {
  onSelectRoute?: (record: RouteHistoryItem) => void
}) {
  const [history, setHistory] = useState<RouteHistoryItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'APPROVED' | 'HARD_BLOCKED'>('ALL')
  const [evidence, setEvidence] = useState<RouteEvidence | null>(null)
  const [loadingEvidence, setLoadingEvidence] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchRouteHistory().then(setHistory).catch(() => setError('Owner-scoped route history could not be loaded.'))
  }, [])

  const filtered = useMemo(() => history.filter((record) => {
    const needle = searchTerm.toLowerCase()
    const matchesSearch = record.source_station_code.toLowerCase().includes(needle)
      || record.dest_station_code.toLowerCase().includes(needle)
    return matchesSearch && (filterStatus === 'ALL' || record.status === filterStatus)
  }), [history, searchTerm, filterStatus])

  const inspect = async (record: RouteHistoryItem) => {
    onSelectRoute?.(record)
    setLoadingEvidence(true)
    setError(null)
    try {
      setEvidence(await fetchRouteEvidence(record.id))
    } catch {
      setError('Stored SourceLine evidence could not be loaded for this route.')
    } finally {
      setLoadingEvidence(false)
    }
  }

  const exportCSV = () => {
    if (!history.length) return
    const headers = 'Route ID,Timestamp,Origin,Destination,Status,Dispatch Status,RRI,Height(m),Width(m),Weight(T)\n'
    const rows = history.map((record) => [
      record.id, record.created_at, record.source_station_code, record.dest_station_code,
      record.status, record.dispatch_status, record.reliability_score,
      record.cargo_height_requested, record.cargo_width_requested, record.cargo_weight_requested,
    ].map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([headers + rows], { type: 'text/csv' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `clearpath-owner-route-history-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 text-slate-100 shadow-xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h2 className="text-xl font-bold">Route Decision History</h2><p className="mt-1 text-xs text-slate-400">Owner-scoped backend records with immutable SourceLine evidence.</p></div>
        <button onClick={exportCSV} disabled={!history.length} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-cyan-300 disabled:opacity-40">Export CSV</button>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search station code" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs" />
        {(['ALL', 'APPROVED', 'HARD_BLOCKED'] as const).map((status) => <button key={status} onClick={() => setFilterStatus(status)} className={`rounded-lg border px-3 py-2 text-xs ${filterStatus === status ? 'border-cyan-500 bg-cyan-950 text-cyan-300' : 'border-slate-700 text-slate-400'}`}>{status}</button>)}
      </div>
      {error ? <p className="mt-4 rounded-lg border border-rose-800 bg-rose-950/20 p-3 text-xs text-rose-300">{error}</p> : null}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-800 text-slate-500"><tr><th className="p-3">Created</th><th className="p-3">Corridor</th><th className="p-3">State</th><th className="p-3">RRI</th><th className="p-3 text-right">Evidence</th></tr></thead>
          <tbody className="divide-y divide-slate-800">
            {filtered.map((record) => <tr key={record.id} className="hover:bg-slate-800/40"><td className="p-3 text-slate-400">{new Date(record.created_at).toLocaleString()}</td><td className="p-3 font-semibold">{record.source_station_code} → {record.dest_station_code}</td><td className="p-3"><span className={record.status === 'APPROVED' ? 'text-emerald-300' : 'text-rose-300'}>{record.status}</span> · {record.dispatch_status}</td><td className="p-3 font-bold">{record.reliability_score}/100</td><td className="p-3 text-right"><button onClick={() => void inspect(record)} className="font-semibold text-cyan-400 hover:underline">Inspect stored evidence</button></td></tr>)}
          </tbody>
        </table>
        {!filtered.length ? <p className="p-8 text-center text-sm text-slate-500">No matching backend route decisions.</p> : null}
      </div>

      {loadingEvidence ? <p className="mt-4 text-xs text-cyan-300">Loading stored evidence…</p> : null}
      {evidence ? <div className="fixed inset-0 z-[1000] flex justify-end bg-slate-950/80" onClick={() => setEvidence(null)}><aside className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-700 bg-slate-950 p-5" onClick={(event) => event.stopPropagation()}><div className="flex justify-between"><div><h3 className="text-xl font-bold">Historical decision evidence</h3><p className="text-xs text-slate-400">Traceability {evidence.traceability.traceability.traced}/{evidence.traceability.traceability.total}</p></div><button onClick={() => setEvidence(null)} className="text-sm text-slate-400">Close</button></div><div className="mt-5 space-y-3">{evidence.components.map((component) => <article key={component.role} className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="flex justify-between gap-3"><h4 className="font-semibold">{component.label}</h4><span className="text-xs text-cyan-300">{component.status}</span></div><p className="mt-1 text-xs text-slate-400">{component.explanation}</p><ul className="mt-3 space-y-1">{evidence.records.filter((record) => component.record_ids.includes(record.id)).map((record) => <li key={record.id} className="rounded bg-slate-950 p-2 text-[11px] text-slate-300"><span className="font-mono text-cyan-300">{record.entity_type}</span> · {record.source?.label ?? 'Derived'} · {record.raw_source_state ?? record.canonical_source_type} · {record.freshness.state}</li>)}</ul></article>)}</div></aside></div> : null}
    </section>
  )
}
