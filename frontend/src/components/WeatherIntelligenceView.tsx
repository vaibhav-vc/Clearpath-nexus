import { useState, useEffect } from 'react'
import { api } from '../services/api'

interface EnvironmentalData {
  weather: {
    weather: { id: number; main: string; description: string }[]
    main: { temp: number; visibility: number; humidity?: number }
    wind: { speed: number }
  }
  space_weather: {
    kp_index: number
    alert_level: string
    issue_datetime: string
  }
  weather_score: number
  alerts: string[]
}

const NODES = [
  { name: 'Nagpur Hub (NGP)', lat: 21.1458, lon: 79.0882 },
  { name: 'Bhusaval Junction (BSL)', lat: 21.0455, lon: 75.7849 },
  { name: 'Manmad Junction (MMR)', lat: 20.25, lon: 74.4333 },
  { name: 'Kalyan Hub (KYN)', lat: 19.2433, lon: 73.1305 },
  { name: 'JNPT Maritime Port (JNPT)', lat: 18.9497, lon: 72.9512 },
]

export default function WeatherIntelligenceView() {
  const [selectedNode, setSelectedNode] = useState(NODES[0])
  const [data, setData] = useState<EnvironmentalData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    setLoading(true)
    setError(null)

    api
      .get<EnvironmentalData>('/weather/environmental', {
        params: { lat: selectedNode.lat, lon: selectedNode.lon },
      })
      .then(({ data: json }) => {
        if (isMounted) setData(json)
      })
      .catch((err: unknown) => {
        if (isMounted) setError(err instanceof Error ? err.message : 'Weather request failed')
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [selectedNode])

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <span>🌦️</span> Multi-Layer Weather & Telemetry Intelligence
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Live Open-Meteo weather & NOAA Space-Weather (Kp Index) feed for critical freight nodes
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {NODES.map((n) => (
              <button
                key={n.name}
                onClick={() => setSelectedNode(n)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  selectedNode.name === n.name
                    ? 'bg-cyan-500 text-slate-950 font-bold shadow-lg shadow-cyan-500/20'
                    : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200'
                }`}
              >
                {n.name.split(' ')[0]}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm animate-pulse">
            Fetching satellite & NOAA space-weather telemetry...
          </div>
        ) : error ? (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
            {error}
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Weather Score Card */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Node Weather Score
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-cyan-400">
                    {data.weather_score}
                  </span>
                  <span className="text-xs text-slate-400">/ 100</span>
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  {selectedNode.name} environmental health
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 text-xs text-slate-300">
                <span className="text-slate-400">Condition:</span>{' '}
                <span className="font-semibold capitalize text-slate-100">
                  {data.weather.weather[0]?.description || 'Clear sky'}
                </span>
              </div>
            </div>

            {/* Space Weather Card */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span>Space Weather (NOAA)</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      data.space_weather.kp_index >= 7
                        ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                        : data.space_weather.kp_index >= 5
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                        : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    }`}
                  >
                    Kp {data.space_weather.kp_index}
                  </span>
                </div>

                <div className="flex items-baseline gap-2">
                  <span
                    className={`text-4xl font-extrabold ${
                      data.space_weather.kp_index >= 5 ? 'text-amber-400' : 'text-emerald-400'
                    }`}
                  >
                    {data.space_weather.kp_index >= 7
                      ? 'Geomagnetic Storm'
                      : data.space_weather.kp_index >= 5
                      ? 'Unsettled'
                      : 'Quiet'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  Telemetry signal degradation & radio blackout risk
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400">
                Issued: {data.space_weather.issue_datetime}
              </div>
            </div>

            {/* Metrics Breakdown */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Atmospheric Indicators
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Temperature</span>
                    <span className="font-semibold text-slate-100">
                      {Math.round(data.weather.main.temp)}°C
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Wind Velocity</span>
                    <span className="font-semibold text-slate-100">
                      {Math.round(data.weather.wind.speed * 3.6)} km/h
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Visibility</span>
                    <span className="font-semibold text-slate-100">
                      {(data.weather.main.visibility / 1000).toFixed(1)} km
                    </span>
                  </div>
                </div>
              </div>

              {data.alerts.length > 0 && (
                <div className="mt-3 p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-[11px] text-amber-300">
                  ⚠️ {data.alerts[0]}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
