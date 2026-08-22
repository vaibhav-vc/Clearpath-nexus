import { useState } from 'react'
import { api } from '../services/api'

interface DelayPredictionData {
  predicted_delay_minutes: number
  confidence_pct: number
  risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
  primary_bottleneck_segment: string
  weather_impact_pct: number
  congestion_impact_pct: number
  optimal_dispatch_window: string
}

export default function PredictiveDelayPanel({
  sourceCode = 'NGP',
  destCode = 'JNPT',
  cargoWeight = 120,
}: {
  sourceCode?: string
  destCode?: string
  cargoWeight?: number
}) {
  const [data, setData] = useState<DelayPredictionData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runPrediction = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data: json } = await api.post<DelayPredictionData>('/predictive/delay', {
          source_code: sourceCode,
          dest_code: destCode,
          cargo_weight: cargoWeight,
          train_arrival_hours: 24,
      })
      setData(json)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Prediction request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl text-slate-100">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <span>⚡</span> AI Delay & Bottleneck Predictive Analytics
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Machine learning forecast of corridor delay minutes, bottleneck risks, & dispatch windows
          </p>
        </div>
        <button
          onClick={runPrediction}
          disabled={loading}
          className="px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-slate-950 font-bold text-xs rounded-xl shadow-lg transition-all disabled:opacity-50"
        >
          {loading ? 'Running AI Engine...' : '⚡ Run AI Delay Forecast'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
          {error}
        </div>
      )}

      {data ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Main Delay Forecast Card */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Forecasted Corridor Delay
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-amber-400">
                  +{data.predicted_delay_minutes} min
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                Confidence Rating: <span className="text-slate-200 font-bold">{data.confidence_pct}%</span>
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <span className="text-xs text-slate-400">Corridor Risk:</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  data.risk_level === 'CRITICAL'
                    ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                    : data.risk_level === 'HIGH'
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                }`}
              >
                {data.risk_level} RISK
              </span>
            </div>
          </div>

          {/* Bottleneck & Dispatch Window Card */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Primary Bottleneck Segment
              </div>
              <div className="text-sm font-bold text-slate-100">
                🚨 {data.primary_bottleneck_segment}
              </div>
              <p className="text-xs text-slate-400 mt-3">
                Optimal Dispatch Window:
              </p>
              <div className="mt-1 text-xs font-semibold text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 p-2 rounded-lg">
                {data.optimal_dispatch_window}
              </div>
            </div>
          </div>

          {/* Impact Drivers Breakdown */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Delay Drivers Weight
              </div>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Weather & Hazards</span>
                    <span className="text-slate-200 font-semibold">{data.weather_impact_pct}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-500 rounded-full"
                      style={{ width: `${data.weather_impact_pct}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Track Congestion</span>
                    <span className="text-slate-200 font-semibold">{data.congestion_impact_pct}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full"
                      style={{ width: `${data.congestion_impact_pct}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-8 text-center bg-slate-950/50 border border-slate-800/80 rounded-xl text-slate-400 text-sm">
          Click <span className="text-amber-400 font-semibold">"Run AI Delay Forecast"</span> to calculate delay probabilities for corridor {sourceCode} → {destCode}.
        </div>
      )}
    </div>
  )
}
