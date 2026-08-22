/**
 * useRouteWeather.ts
 * Hook that fetches live per-point weather data from Open-Meteo for all
 * sampled points along the active route. Powers the Route Weather Database panel.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { SegmentPath, Station } from '../types/route'
import { sampleRoutePoints } from '../services/weatherConditions'
import { fetchRouteWeatherPoints } from '../services/api'

export interface RouteWeatherPoint {
  id: string
  label: string
  lat: number
  lon: number
  temperature: number
  feelsLike: number
  humidity: number
  windSpeed: number
  windDirection: number
  visibility: number // metres
  uvIndex: number
  weatherCode: number
  weatherLabel: string
  precipMm: number
  condition: 'clear' | 'rain' | 'storm' | 'snow' | 'fog' | 'cloudy' | 'windy'
}

const POLL_MS = 10 * 60 * 1000 // 10 minutes

function weatherCodeToLabel(code: number): string {
  if (code === 0) return 'Clear sky'
  if (code === 1) return 'Mainly clear'
  if (code === 2) return 'Partly cloudy'
  if (code === 3) return 'Overcast'
  if (code === 45) return 'Foggy'
  if (code === 48) return 'Icy fog'
  if (code >= 51 && code <= 55) return 'Drizzle'
  if (code >= 56 && code <= 57) return 'Freezing drizzle'
  if (code >= 61 && code <= 65) return code >= 63 ? 'Heavy rain' : 'Moderate rain'
  if (code >= 66 && code <= 67) return 'Freezing rain'
  if (code >= 71 && code <= 77) return 'Snow'
  if (code >= 80 && code <= 82) return 'Rain showers'
  if (code >= 85 && code <= 86) return 'Snow showers'
  if (code >= 95 && code <= 99) return code >= 96 ? 'Hail storm' : 'Thunderstorm'
  return 'Cloudy'
}

function weatherCodeToCondition(code: number): RouteWeatherPoint['condition'] {
  if (code === 0 || code === 1) return 'clear'
  if (code === 2 || code === 3) return 'cloudy'
  if (code === 45 || code === 48) return 'fog'
  if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return 'rain'
  if (code >= 71 && code <= 77) return 'snow'
  if (code >= 95) return 'storm'
  return 'cloudy'
}

function idToLabel(id: string, stations: Station[]): string {
  // Try to match a station code like "st-NGP"
  const stMatch = id.match(/^st-(.+)$/)
  if (stMatch) {
    const code = stMatch[1]
    const station = stations.find((s) => s.code === code)
    if (station) return `${station.code} — ${station.name}`
    return code
  }
  // Segment midpoints like "seg-xxx-mid"
  if (id.endsWith('-mid')) return 'Route midpoint'
  if (id.endsWith('-start')) return 'Segment start'
  if (id.endsWith('-end')) return 'Segment end'
  return id
}

function toRouteWeatherPoint(
  weather: {
    id: string
    lat: number
    lon: number
    temperature_2m: number
    apparent_temperature: number
    relative_humidity_2m: number
    weather_code: number
    wind_speed_10m: number
    wind_direction_10m: number
    visibility: number
    uv_index: number
    precipitation: number
  },
  stations: Station[],
): RouteWeatherPoint {
  return {
    id: weather.id,
    label: idToLabel(weather.id, stations),
    lat: weather.lat,
    lon: weather.lon,
    temperature: Math.round(weather.temperature_2m * 10) / 10,
    feelsLike: Math.round(weather.apparent_temperature * 10) / 10,
    humidity: Math.round(weather.relative_humidity_2m),
    windSpeed: Math.round(weather.wind_speed_10m),
    windDirection: Math.round(weather.wind_direction_10m),
    visibility: weather.visibility,
    uvIndex: Math.round(weather.uv_index * 10) / 10,
    weatherCode: weather.weather_code,
    weatherLabel: weatherCodeToLabel(weather.weather_code),
    precipMm: Math.round(weather.precipitation * 10) / 10,
    condition: weatherCodeToCondition(weather.weather_code),
  }
}

export function useRouteWeather(
  segments: SegmentPath[],
  stations: Station[],
  enabled = true,
) {
  const [points, setPoints] = useState<RouteWeatherPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    if (!enabled || (segments.length === 0 && stations.length === 0)) return
    setLoading(true)
    setError(null)

    try {
      // Sample up to 8 points across the route
      const sampled = sampleRoutePoints(segments, stations, 8)

      if (sampled.length === 0) {
        setPoints([])
        return
      }

      const response = await fetchRouteWeatherPoints({ points: sampled })
      const available = response.points.filter((point: { available: boolean }) => point.available)
      const unavailable = response.points.filter((point: { available: boolean }) => !point.available)
      const fetched = available.map((point: Parameters<typeof toRouteWeatherPoint>[0]) =>
        toRouteWeatherPoint(point, stations),
      )

      setPoints(fetched)
      setLastUpdated(new Date())
      if (unavailable.length > 0) {
        setError(`${unavailable.length} point(s) are unavailable; do not use missing records for dispatch decisions.`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Weather fetch failed')
    } finally {
      setLoading(false)
    }
  }, [segments, stations, enabled])

  useEffect(() => {
    refresh()
    timerRef.current = setInterval(refresh, POLL_MS)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [refresh])

  return { points, loading, lastUpdated, error, refresh }
}
