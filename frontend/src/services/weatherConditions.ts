import type { ConditionType } from '../maps/conditionSymbols'
import type { MapCondition, SegmentPath, Station } from '../types/route'
import { fetchMapConditions } from './api'

export interface OpenMeteoCurrent {
  temperature_2m: number
  relative_humidity_2m: number
  weather_code: number
  wind_speed_10m: number
  visibility: number
  uv_index: number
}

const OPEN_METEO =
  'https://api.open-meteo.com/v1/forecast?current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,visibility,uv_index&timezone=auto'

const NOAA_KP = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json'

function primaryWeatherType(code: number): ConditionType {
  if (code === 0) return 'clear'
  if (code === 1) return 'partly_cloudy'
  if (code === 2 || code === 3) return 'cloudy'
  if (code === 45) return 'mist'
  if (code === 48) return 'fog'
  if (code >= 51 && code <= 57) return 'light_rain'
  if (code >= 61 && code <= 65) return code >= 63 ? 'heavy_rain' : 'light_rain'
  if (code >= 66 && code <= 67) return 'sleet'
  if (code >= 71 && code <= 77) return 'snow'
  if (code >= 80 && code <= 82) return 'heavy_rain'
  if (code >= 85 && code <= 86) return 'snow'
  if (code >= 95 && code <= 99) return code >= 96 ? 'hail' : 'thunderstorm'
  return 'cloudy'
}

export function mapWeatherToConditions(
  data: OpenMeteoCurrent,
  lat: number,
  lon: number,
  pointId: string,
): MapCondition[] {
  const conditions: MapCondition[] = []
  const primary = primaryWeatherType(data.weather_code)
  const meta = { lat, lon }

  conditions.push({
    id: `${pointId}-${primary}`,
    type: primary,
    category: 'weather',
    reading: `${Math.round(data.temperature_2m)}°C`,
    ...meta,
  })

  if (data.wind_speed_10m >= 20) {
    conditions.push({
      id: `${pointId}-high_winds`,
      type: 'high_winds',
      category: 'weather',
      reading: `${Math.round(data.wind_speed_10m)} km/h`,
      ...meta,
    })
  } else if (data.wind_speed_10m >= 10) {
    conditions.push({
      id: `${pointId}-strong_wind`,
      type: 'strong_wind',
      category: 'weather',
      reading: `${Math.round(data.wind_speed_10m)} km/h`,
      ...meta,
    })
  }

  if (data.temperature_2m >= 35) {
    conditions.push({
      id: `${pointId}-high_temp`,
      type: 'high_temp',
      category: 'weather',
      reading: `${Math.round(data.temperature_2m)}°C`,
      ...meta,
    })
  } else if (data.temperature_2m <= 5) {
    conditions.push({
      id: `${pointId}-low_temp`,
      type: 'low_temp',
      category: 'weather',
      reading: `${Math.round(data.temperature_2m)}°C`,
      ...meta,
    })
  }

  if (data.relative_humidity_2m >= 85) {
    conditions.push({
      id: `${pointId}-high_humidity`,
      type: 'high_humidity',
      category: 'weather',
      reading: `${Math.round(data.relative_humidity_2m)}%`,
      ...meta,
    })
  } else if (data.relative_humidity_2m <= 30) {
    conditions.push({
      id: `${pointId}-low_humidity`,
      type: 'low_humidity',
      category: 'weather',
      reading: `${Math.round(data.relative_humidity_2m)}%`,
      ...meta,
    })
  }

  if (data.visibility > 0 && data.visibility < 2000) {
    conditions.push({
      id: `${pointId}-low_visibility`,
      type: 'low_visibility',
      category: 'weather',
      reading: `${(data.visibility / 1000).toFixed(1)} km`,
      ...meta,
    })
  }

  if (data.uv_index >= 8) {
    conditions.push({
      id: `${pointId}-high_uv`,
      type: 'high_uv',
      category: 'weather',
      reading: `UV ${Math.round(data.uv_index)}`,
      ...meta,
    })
  }

  if (data.temperature_2m <= 2 && data.weather_code >= 51 && data.weather_code <= 67) {
    conditions.push({
      id: `${pointId}-icing`,
      type: 'icing',
      category: 'weather',
      ...meta,
    })
  }

  if (data.weather_code >= 95) {
    conditions.push({
      id: `${pointId}-storm_warning`,
      type: 'storm_warning',
      category: 'environmental',
      ...meta,
    })
  }

  if (data.weather_code >= 63 && data.relative_humidity_2m > 80) {
    conditions.push({
      id: `${pointId}-flood_risk`,
      type: 'flood_risk',
      category: 'environmental',
      ...meta,
    })
  }

  if (data.visibility > 0 && data.visibility < 3000 && data.wind_speed_10m > 8 && data.relative_humidity_2m < 40) {
    conditions.push({
      id: `${pointId}-dust`,
      type: 'dust',
      category: 'weather',
      ...meta,
    })
  }

  if (data.visibility > 0 && data.visibility < 4000 && data.relative_humidity_2m > 70 && primary !== 'fog') {
    conditions.push({
      id: `${pointId}-air_pollution`,
      type: 'air_pollution',
      category: 'environmental',
      ...meta,
    })
  }

  return conditions
}

async function fetchOpenMeteo(lat: number, lon: number): Promise<OpenMeteoCurrent> {
  const url = `${OPEN_METEO}&latitude=${lat}&longitude=${lon}`
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Open-Meteo error ${resp.status}`)
  const json = await resp.json()
  return json.current as OpenMeteoCurrent
}

async function fetchKpIndex(): Promise<number> {
  try {
    const resp = await fetch(NOAA_KP)
    if (!resp.ok) return 2
    const rows: string[][] = await resp.json()
    if (!Array.isArray(rows) || rows.length < 2) return 2
    const latest = rows[rows.length - 1]
    return parseInt(latest[1], 10) || 2
  } catch {
    return 2
  }
}

export function sampleRoutePoints(
  segments: SegmentPath[],
  stations: Station[],
  maxPoints = 6,
): { lat: number; lon: number; id: string }[] {
  const raw: { lat: number; lon: number; id: string }[] = []

  segments.forEach((seg) => {
    const coords = seg.coordinates
    if (coords.length === 0) return
    raw.push({ lat: coords[0][0], lon: coords[0][1], id: `${seg.id}-start` })
    if (coords.length > 2) {
      const mid = coords[Math.floor(coords.length / 2)]
      raw.push({ lat: mid[0], lon: mid[1], id: `${seg.id}-mid` })
    }
    const end = coords[coords.length - 1]
    raw.push({ lat: end[0], lon: end[1], id: `${seg.id}-end` })
  })

  stations.forEach((s) => {
    raw.push({ lat: s.lat, lon: s.lon, id: `st-${s.code}` })
  })

  const deduped: { lat: number; lon: number; id: string }[] = []
  const seen = new Set<string>()
  for (const p of raw) {
    const key = `${p.lat.toFixed(1)}:${p.lon.toFixed(1)}`
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(p)
  }

  return deduped.slice(0, maxPoints)
}

function deriveOperationalConditions(
  segments: SegmentPath[],
  stations: Station[],
  destinationCode?: string,
): MapCondition[] {
  const conditions: MapCondition[] = []

  stations.forEach((s) => {
    conditions.push({
      id: `op-station-${s.code}`,
      type: 'station_active',
      category: 'operational',
      lat: s.lat,
      lon: s.lon,
    })
  })

  if (destinationCode === 'JNPT') {
    const port = stations.find((s) => s.code === 'JNPT')
    if (port) {
      conditions.push({
        id: 'op-port-jnpt',
        type: 'port_active',
        category: 'operational',
        lat: port.lat,
        lon: port.lon,
      })
    }
  }

  segments.forEach((seg) => {
    if (seg.coordinates.length === 0) return
    const mid = seg.coordinates[Math.floor(seg.coordinates.length / 2)]
    if (seg.status === 'HARD_BLOCKED') {
      conditions.push({
        id: `op-block-${seg.id}`,
        type: 'track_blocked',
        category: 'operational',
        lat: mid[0],
        lon: mid[1],
      })
    } else if (seg.phase === 'CURRENT') {
      conditions.push({
        id: `op-current-${seg.id}`,
        type: 'track_clear',
        category: 'operational',
        lat: mid[0],
        lon: mid[1],
      })
    } else if (seg.status === 'APPROVED' && seg.phase === 'UPCOMING') {
      conditions.push({
        id: `op-upcoming-${seg.id}`,
        type: 'track_caution',
        category: 'operational',
        lat: mid[0],
        lon: mid[1],
      })
    }
  })

  return conditions
}

function offsetMarkerPosition(
  lat: number,
  lon: number,
  index: number,
): { lat: number; lon: number } {
  const angle = (index * 137.5 * Math.PI) / 180
  const radius = 0.04 + index * 0.015
  return {
    lat: lat + Math.cos(angle) * radius,
    lon: lon + Math.sin(angle) * radius,
  }
}

export async function fetchLiveMapConditions(opts: {
  segments: SegmentPath[]
  stations: Station[]
  destinationCode?: string
}): Promise<MapCondition[]> {
  const points = sampleRoutePoints(opts.segments, opts.stations)
  const allConditions: MapCondition[] = []

  if (points.length === 0) {
    return allConditions
  }

  const weatherResults = await Promise.allSettled(
    points.map(async (p) => {
      const data = await fetchOpenMeteo(p.lat, p.lon)
      return mapWeatherToConditions(data, p.lat, p.lon, p.id)
    }),
  )

  weatherResults.forEach((result, i) => {
    if (result.status === 'fulfilled') {
      result.value.forEach((c, j) => {
        const pos = offsetMarkerPosition(c.lat, c.lon, j)
        allConditions.push({ ...c, lat: pos.lat, lon: pos.lon })
      })
    } else {
      console.warn(`Weather fetch failed for point ${points[i]?.id}:`, result.reason)
    }
  })

  const kp = await fetchKpIndex()
  if (kp >= 5 && points.length > 0) {
    const p = points[0]
    allConditions.push({
      id: 'solar-kp',
      type: 'solar',
      category: 'weather',
      lat: p.lat + 0.05,
      lon: p.lon + 0.05,
      reading: `Kp ${kp}`,
      detail: kp >= 7 ? 'Critical geomagnetic activity' : 'Elevated Kp-index',
    })
  }

  const operational = deriveOperationalConditions(opts.segments, opts.stations, opts.destinationCode)
  allConditions.push(...operational)

  if (allConditions.filter((c) => c.category !== 'operational').length === 0) {
    const p = points[0]
    allConditions.push({
      id: 'all-clear',
      type: 'all_clear',
      category: 'operational',
      lat: p.lat,
      lon: p.lon,
    })
  }

  return allConditions
}

export async function fetchMapConditionsFromApi(
  segments: SegmentPath[],
  stations: Station[],
  destinationCode?: string,
): Promise<MapCondition[] | null> {
  try {
    const points = sampleRoutePoints(segments, stations)
    const data = await fetchMapConditions({ points, destination_code: destinationCode })
    return data.conditions as MapCondition[]
  } catch {
    return null
  }
}

export async function resolveMapConditions(opts: {
  segments: SegmentPath[]
  stations: Station[]
  destinationCode?: string
}): Promise<MapCondition[]> {
  const fromApi = await fetchMapConditionsFromApi(opts.segments, opts.stations, opts.destinationCode)
  if (fromApi) return fromApi
  throw new Error('Map-condition provider is unavailable; no operational fallback is shown.')
}
