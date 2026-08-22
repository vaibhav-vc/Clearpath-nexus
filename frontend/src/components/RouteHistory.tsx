import { useCallback, useEffect, useState } from 'react'
import { dispatchRoute, fetchRouteHistory } from '../services/api'
import type { RouteHistoryItem } from '../types/route'

interface Props {
  onBack: () => void
  onSchedule: () => void
}

export default function RouteHistory({ onBack, onSchedule }: Props) {
  const [items, setItems] = useState<RouteHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await fetchRouteHistory())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load route history')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const dispatch = async (route: RouteHistoryItem) => {
    try {
      const result = await dispatchRoute(route.id)
      setItems((prev) => prev.map((item) => item.id === route.id ? { ...item, dispatch_status: 'DISPATCHED', dispatched_at: result.dispatched_at } : item))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Dispatch failed')
    }
  }

  return (
    <div className="min-h-screen bg-[#121a2e] text-white">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-blue-800/60 bg-gradient-to-r from-blue-950 via-blue-900 to-indigo-950 px-6 py-4">
        <div>
          <h1 className="text-xl font-bold">Route History / Dispatch Log</h1>
          <p className="text-xs font-mono text-blue-300">Supabase-user scoped route evaluations</p>
        </div>
        <div className="flex gap-2">
          <button onClick={onBack} className="rounded border border-slate-600 px-3 py-2 text-xs font-mono hover:bg-slate-800">Route Planner</button>
          <button onClick={onSchedule} className="rounded border border-blue-500/50 px-3 py-2 text-xs font-mono text-blue-300 hover:bg-blue-950/50">Scheduler</button>
          <button onClick={() => void load()} className="rounded bg-blue-600 px-3 py-2 text-xs font-mono hover:bg-blue-500">Refresh</button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl p-6">
        {error ? <div className="mb-4 rounded border border-red-600/40 bg-red-950/30 p-3 text-sm text-red-300">{error}</div> : null}
        {loading ? <p className="font-mono text-slate-400">Loading dispatch log…</p> : null}
        {!loading && items.length === 0 ? <p className="rounded border border-slate-700 bg-slate-900 p-4 font-mono text-sm text-slate-400">No evaluations yet. Run a route from the planner first.</p> : null}
        <div className="overflow-x-auto rounded-xl border border-slate-700 bg-slate-900/80">
          {items.length > 0 ? (
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-slate-700 bg-slate-950/60 text-[10px] font-mono uppercase text-slate-400">
                <tr>
                  <th className="p-3">Created</th><th className="p-3">Route</th><th className="p-3">Cargo H×W / T</th><th className="p-3">Clearance</th><th className="p-3">Reliability</th><th className="p-3">Dispatch</th><th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-800 last:border-0">
                    <td className="p-3 font-mono text-xs text-slate-400">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="p-3 font-mono font-bold text-blue-300">{item.source_station_code} → {item.dest_station_code}</td>
                    <td className="p-3 font-mono text-xs">{item.cargo_height_requested}×{item.cargo_width_requested}m / {item.cargo_weight_requested}T</td>
                    <td className="p-3"><span className={item.status === 'APPROVED' ? 'text-emerald-300' : 'text-red-300'}>{item.status}</span></td>
                    <td className="p-3 font-mono">{item.reliability_score}%</td>
                    <td className="p-3 font-mono text-xs">{item.dispatch_status}</td>
                    <td className="p-3">
                      <button
                        onClick={() => void dispatch(item)}
                        disabled={item.status !== 'APPROVED' || item.dispatch_status === 'DISPATCHED'}
                        className="rounded bg-emerald-700 px-3 py-2 text-xs font-semibold hover:bg-emerald-600 disabled:opacity-40"
                      >
                        {item.dispatch_status === 'DISPATCHED' ? 'Dispatched' : 'Dispatch'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      </main>
    </div>
  )
}
