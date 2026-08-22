import { useCallback, useEffect, useState } from 'react'
import { dispatchSchedule, fetchSchedules, synchronizeTrainSchedule, type TrainSyncState } from '../services/api'
import type { TrainSchedule } from '../types/route'

interface Props {
  onBack: () => void
  onHistory: () => void
}

const badgeClass: Record<string, string> = {
  CLEAR: 'border-emerald-500/40 bg-emerald-950/40 text-emerald-300',
  WARNING: 'border-amber-500/40 bg-amber-950/40 text-amber-300',
  BLOCKED: 'border-red-500/40 bg-red-950/40 text-red-300',
}

export default function ScheduleBoard({ onBack, onHistory }: Props) {
  const [items, setItems] = useState<TrainSchedule[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncStates, setSyncStates] = useState<Record<string, TrainSyncState>>({})
  const [syncing, setSyncing] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await fetchSchedules())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load schedules')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const dispatch = async (id: string) => {
    setError(null)
    try {
      const updated = await dispatchSchedule(id)
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Dispatch failed')
    }
  }

  const synchronize = async (id: string) => {
    setSyncing(id)
    setError(null)
    try {
      const state = await synchronizeTrainSchedule(id)
      setSyncStates((current) => ({ ...current, [id]: state }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Train synchronization failed')
    } finally {
      setSyncing(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#121a2e] text-white">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-blue-800/60 bg-gradient-to-r from-blue-950 via-blue-900 to-indigo-950 px-6 py-4">
        <div>
          <h1 className="text-xl font-bold">Train Scheduling Control</h1>
          <p className="text-xs font-mono text-blue-300">Owned schedules · optional authorized ixigo passenger status · shared FastAPI state</p>
        </div>
        <div className="flex gap-2">
          <button onClick={onBack} className="rounded border border-slate-600 px-3 py-2 text-xs font-mono hover:bg-slate-800">Route Planner</button>
          <button onClick={onHistory} className="rounded border border-blue-500/50 px-3 py-2 text-xs font-mono text-blue-300 hover:bg-blue-950/50">Dispatch Log</button>
          <button onClick={() => void load()} className="rounded bg-blue-600 px-3 py-2 text-xs font-mono hover:bg-blue-500">Refresh</button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-6">
        {error ? <div className="mb-4 rounded border border-red-600/40 bg-red-950/30 p-3 text-sm text-red-300">{error}</div> : null}
        {loading ? <p className="font-mono text-slate-400">Loading schedules…</p> : null}
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <article key={item.id} className="rounded-xl border border-slate-700 bg-slate-900/80 p-5 shadow-xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-mono text-lg font-bold text-blue-300">{item.train_code}</h2>
                    {item.is_demo ? <span className="rounded bg-slate-700 px-2 py-0.5 text-[9px] font-mono uppercase text-slate-300">Demo</span> : null}
                  </div>
                  <p className="text-sm text-slate-300">{item.train_name}</p>
                  <p className="mt-2 font-mono text-sm">{item.source_station_code} → {item.dest_station_code}</p>
                </div>
                <span className={`rounded-full border px-2.5 py-1 text-[10px] font-mono font-bold ${badgeClass[item.conflict_status] ?? badgeClass.WARNING}`}>
                  {item.conflict_status}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 rounded-lg bg-slate-950/60 p-3 font-mono text-xs">
                <div><span className="block text-slate-500">Departure</span>{new Date(item.scheduled_departure).toLocaleString()}</div>
                <div><span className="block text-slate-500">Arrival</span>{new Date(item.scheduled_arrival).toLocaleString()}</div>
                <div><span className="block text-slate-500">State</span>{item.schedule_status}</div>
                <div><span className="block text-slate-500">Berth window</span>{item.berth_window_start ? 'Operator supplied' : 'Not supplied'}</div>
              </div>

              {item.conflict_reason ? (
                <div className="mt-3 rounded-lg border border-slate-700 bg-slate-950/50 p-3 text-xs font-mono text-slate-300">
                  {item.conflict_reason}
                </div>
              ) : null}

              {syncStates[item.id] ? <div className="mt-3 rounded-lg border border-cyan-800 bg-cyan-950/20 p-3 text-xs font-mono">
                <div className="flex items-center justify-between"><span className="text-cyan-300">ixigo supplementary sync</span><span className="text-amber-300">{syncStates[item.id].status}</span></div>
                <p className="mt-1 text-slate-400">{syncStates[item.id].current_station ?? 'Position unavailable'} · delay {syncStates[item.id].delay_minutes ?? 'UNAVAILABLE'} min · {syncStates[item.id].freshness}</p>
                <p className="mt-2 text-[10px] text-slate-500">{syncStates[item.id].authority_notice}</p>
              </div> : null}

              <button type="button" onClick={() => void synchronize(item.id)} disabled={syncing === item.id} className="mt-4 w-full rounded-lg border border-cyan-700 px-4 py-2 text-xs font-semibold text-cyan-300 disabled:opacity-40">
                {syncing === item.id ? 'Synchronizing…' : 'Sync supplementary train status'}
              </button>

              <button
                type="button"
                onClick={() => void dispatch(item.id)}
                disabled={item.conflict_status === 'BLOCKED' || item.schedule_status === 'DISPATCHED' || item.schedule_status === 'CANCELLED'}
                className="mt-4 w-full rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-3 text-sm font-semibold transition hover:from-emerald-500 hover:to-teal-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {item.schedule_status === 'DISPATCHED' ? 'Dispatched' : item.conflict_status === 'BLOCKED' ? 'Dispatch Blocked' : 'Finalize & Dispatch Train'}
              </button>
            </article>
          ))}
        </div>
      </main>
    </div>
  )
}
