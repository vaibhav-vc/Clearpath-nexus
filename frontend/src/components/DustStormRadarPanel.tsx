import { useState, useEffect } from 'react'
import { api } from '../services/api'

interface DustRiskData {
  location: string
  lat: number
  lon: number
  dust_risk_index: number
  airborne_particulate_pm10: number
  visibility_km: number
  warning_level: 'SAFE' | 'ADVISORY' | 'SEVERE' | 'HAZARD'
  recommended_speed_limit_kmh: number
}

export default function DustStormRadarPanel() {
  const [data, setData] = useState<DustRiskData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    setLoading(true)
    api
      .get<DustRiskData>('/predictive/dust-risk', {
        params: { lat: 21.1458, lon: 79.0882, location: 'Nagpur-Bhusaval Corridor' },
      })
      .then(({ data: json }) => {
        if (isMounted) setData(json)
      })
      .catch((err: unknown) => {
        if (isMounted) setError(err instanceof Error ? err.message : 'Dust risk request failed')
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl text-slate-100">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <span>🌪️</span> Desert Dust Storm & Airborne Particulate Radar
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time airborne PM10 hazard analysis & low-visibility speed restrictions
          </p>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-400 text-sm animate-pulse">
          Scanning environmental particulate sensors...
        </div>
      ) : error ? (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
          {error}
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 uppercase font-semibold mb-1">Dust Hazard Index</div>
            <div className="text-3xl font-extrabold text-amber-400">{data.dust_risk_index} / 100</div>
            <div className="text-[11px] text-slate-400 mt-2">Corridor Index Rating</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 uppercase font-semibold mb-1">Airborne PM10 Level</div>
            <div className="text-3xl font-extrabold text-cyan-400">{data.airborne_particulate_pm10} µg/m³</div>
            <div className="text-[11px] text-slate-400 mt-2">Particulate Concentration</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 uppercase font-semibold mb-1">Visibility Range</div>
            <div className="text-3xl font-extrabold text-slate-100">{data.visibility_km} km</div>
            <div className="text-[11px] text-slate-400 mt-2">Optical Sensor Range</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 uppercase font-semibold mb-1">Speed Restriction</div>
            <div className="text-3xl font-extrabold text-emerald-400">max {data.recommended_speed_limit_kmh} km/h</div>
            <div className="text-[11px] text-slate-400 mt-2">Recommended Safety Cap</div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
