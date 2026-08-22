import { useEffect, useState } from 'react'
import { fetchStations, fetchLiveCorridorTraffic, type LiveCorridorTrafficResponse } from '../services/api'
import type { Station } from '../types/route'
import { resolveRemediation } from '../lib/remediation'
import DegradedStateCard from './status/DegradedStateCard'

// Deliberately substring-matched, unlike the shared status vocabulary: this is
// free-text passenger-train status from RailRadar, not a backend enum.
function statusColor(status: string): string {
  const s = status.toLowerCase()
  if (s.includes('late') || s.includes('delay')) return 'text-amber-400'
  if (s.includes('cancel')) return 'text-rose-400'
  if (s.includes('run') || s.includes('on time')) return 'text-emerald-400'
  return 'text-slate-300'
}

export default function LiveCorridorTrafficPanel() {
  const [stations, setStations] = useState<Station[]>([])
  const [sourceCode, setSourceCode] = useState('NGP')
  const [destCode, setDestCode] = useState('JNPT')
  const [data, setData] = useState<LiveCorridorTrafficResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchStations()
      .then(setStations)
      .catch(() => setStations([]))
  }, [])

  const loadTraffic = () => {
    setLoading(true)
    setError(null)
    fetchLiveCorridorTraffic(sourceCode, destCode)
      .then(setData)
      .catch((err) => setError(err.message ?? 'Request failed'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadTraffic()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl text-slate-100">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <span>🛰️</span> Live Corridor Traffic
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
              DEMO INTEGRATION
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Optional live passenger-train layer via a public sandbox API. This tracks
            passenger/PRS trains only — it is not a freight-operations feed and does not
            influence the Route Reliability Index.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 mb-6">
        <div>
          <label className="block text-[11px] text-slate-400 mb-1">From</label>
          <select
            value={sourceCode}
            onChange={(e) => setSourceCode(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
          >
            {stations.map((s) => (
              <option key={s.code} value={s.code}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[11px] text-slate-400 mb-1">To</label>
          <select
            value={destCode}
            onChange={(e) => setDestCode(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-100"
          >
            {stations.map((s) => (
              <option key={s.code} value={s.code}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={loadTraffic}
          disabled={loading}
          className="px-4 py-1.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-md transition-all"
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-400 text-sm animate-pulse">
          Querying live corridor traffic…
        </div>
      ) : error ? (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
          {error}
        </div>
      ) : data && !data.available ? (
        <DegradedStateCard
          variant="soft"
          title="Layer not configured"
          state="NOT_CONFIGURED"
          domain="availability"
          message={data.message}
          hint={resolveRemediation(data.provider, 'NOT_CONFIGURED')}
        />
      ) : data ? (
        <div className="space-y-4">
          {data.alerts.length > 0 && (
            <div className="space-y-1">
              {data.alerts.map((alert, i) => (
                <div
                  key={i}
                  className="p-2 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-300"
                >
                  ⚠️ {alert}
                </div>
              ))}
            </div>
          )}

          {data.trains.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-xs">
              No trains found between {data.source_code} and {data.dest_code} right now.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.trains.map((train) => (
                <div
                  key={train.train_number}
                  className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex items-center justify-between"
                >
                  <div>
                    <div className="text-sm font-bold text-slate-100">{train.train_number}</div>
                    <div className="text-[11px] text-slate-400">{train.train_name}</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-xs font-semibold ${statusColor(train.status)}`}>
                      {train.status}
                    </div>
                    {train.delay_minutes !== null && (
                      <div className="text-[11px] text-slate-400">{train.delay_minutes}m delay</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
