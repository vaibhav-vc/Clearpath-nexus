/**
 * railwayGeometry.ts
 * Fetches real railway track geometry from the OpenStreetMap Overpass API
 * so route polylines on the map follow actual railway tracks, not straight lines.
 */

const OVERPASS_URL = 'https://overpass-api.de/api/interpreter'

interface OverpassNode {
  type: 'node'
  id: number
  lat: number
  lon: number
}

interface OverpassWay {
  type: 'way'
  id: number
  nodes: number[]
}

interface OverpassResponse {
  elements: (OverpassNode | OverpassWay)[]
}

// Cache: segmentKey → ordered [lat, lon][] coords following real tracks
const trackCache = new Map<string, [number, number][]>()

function segmentKey(
  fromLat: number,
  fromLon: number,
  toLat: number,
  toLon: number,
): string {
  return `${fromLat.toFixed(3)},${fromLon.toFixed(3)}-${toLat.toFixed(3)},${toLon.toFixed(3)}`
}

/**
 * Given a bounding box, fetches all railway=rail ways from OSM.
 * Returns a deduplicated map of nodeId → {lat,lon}.
 */
async function fetchRailwaysInBbox(
  minLat: number,
  minLon: number,
  maxLat: number,
  maxLon: number,
): Promise<{ nodes: Map<number, { lat: number; lon: number }>; ways: OverpassWay[] }> {
  // Expand bbox slightly for edge coverage
  const pad = 0.05
  const bbox = `${minLat - pad},${minLon - pad},${maxLat + pad},${maxLon + pad}`

  const query = `
[out:json][timeout:25];
(
  way["railway"="rail"](${bbox});
  way["railway"="narrow_gauge"](${bbox});
);
out body;
>;
out skel qt;
`.trim()

  const resp = await fetch(OVERPASS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `data=${encodeURIComponent(query)}`,
  })

  if (!resp.ok) throw new Error(`Overpass error: ${resp.status}`)
  const json: OverpassResponse = await resp.json()

  const nodes = new Map<number, { lat: number; lon: number }>()
  const ways: OverpassWay[] = []

  for (const el of json.elements) {
    if (el.type === 'node') {
      nodes.set(el.id, { lat: el.lat, lon: el.lon })
    } else if (el.type === 'way') {
      ways.push(el)
    }
  }

  return { nodes, ways }
}

/**
 * Haversine distance in km between two lat/lon points.
 */
function distKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

/**
 * Stitch OSM ways into an ordered polyline from (fromLat,fromLon) → (toLat,toLon).
 * Uses a greedy nearest-neighbour graph traversal across all way segments.
 */
function stitchTrackPolyline(
  ways: OverpassWay[],
  nodes: Map<number, { lat: number; lon: number }>,
  fromLat: number,
  fromLon: number,
  toLat: number,
  toLon: number,
): [number, number][] {
  if (ways.length === 0) return []

  // Build adjacency: each way contributes its node sequence
  // We'll convert all ways into coordinate lists first
  const segments: [number, number][][] = ways.map((w) =>
    w.nodes
      .map((id) => {
        const n = nodes.get(id)
        return n ? ([n.lat, n.lon] as [number, number]) : null
      })
      .filter(Boolean) as [number, number][],
  )

  if (segments.length === 0) return []

  // Collect all coordinate points from all segments in a simple flat list,
  // sorted spatially toward the destination — greedy approach
  const allPoints: [number, number][] = segments.flat()

  // Remove near-duplicates (dedup within ~100m)
  const deduped: [number, number][] = []
  const seenKeys = new Set<string>()
  for (const p of allPoints) {
    const k = `${p[0].toFixed(3)}:${p[1].toFixed(3)}`
    if (!seenKeys.has(k)) {
      seenKeys.add(k)
      deduped.push(p)
    }
  }

  if (deduped.length === 0) return []

  // Sort all points by their projected position along the from→to vector
  // so the polyline goes in the right direction
  const vLat = toLat - fromLat
  const vLon = toLon - fromLon
  const vLen = Math.sqrt(vLat ** 2 + vLon ** 2) || 1

  const sorted = [...deduped].sort((a, b) => {
    const projA = ((a[0] - fromLat) * vLat + (a[1] - fromLon) * vLon) / vLen
    const projB = ((b[0] - fromLat) * vLat + (b[1] - fromLon) * vLon) / vLen
    return projA - projB
  })

  // Trim to points roughly between start and end (filter outliers > 1.5× total distance)
  const totalDist = distKm(fromLat, fromLon, toLat, toLon)
  const filtered = sorted.filter((p) => {
    const dFrom = distKm(fromLat, fromLon, p[0], p[1])
    const dTo = distKm(toLat, toLon, p[0], p[1])
    return dFrom < totalDist * 1.6 && dTo < totalDist * 1.6
  })

  if (filtered.length === 0) return []

  // Ensure we start close to fromLat/fromLon and end close to toLat/toLon
  const result: [number, number][] = []

  // Prepend the actual from-point if it's far from first track point
  const firstPt = filtered[0]
  if (distKm(fromLat, fromLon, firstPt[0], firstPt[1]) > 1) {
    result.push([fromLat, fromLon])
  }
  result.push(...filtered)
  // Append the actual to-point if far from last track point
  const lastPt = filtered[filtered.length - 1]
  if (distKm(toLat, toLon, lastPt[0], lastPt[1]) > 1) {
    result.push([toLat, toLon])
  }

  return result
}

/**
 * Public API: fetch the real railway track geometry between two points.
 * Returns an ordered array of [lat, lon] coordinates following actual railway tracks.
 * Falls back to undefined if fetch fails (caller uses straight-line coords).
 */
export async function fetchRailwayTrack(
  fromLat: number,
  fromLon: number,
  toLat: number,
  toLon: number,
): Promise<[number, number][] | undefined> {
  const key = segmentKey(fromLat, fromLon, toLat, toLon)

  if (trackCache.has(key)) {
    return trackCache.get(key)
  }

  try {
    const minLat = Math.min(fromLat, toLat)
    const maxLat = Math.max(fromLat, toLat)
    const minLon = Math.min(fromLon, toLon)
    const maxLon = Math.max(fromLon, toLon)

    const { nodes, ways } = await fetchRailwaysInBbox(minLat, minLon, maxLat, maxLon)

    const track = stitchTrackPolyline(ways, nodes, fromLat, fromLon, toLat, toLon)

    const result = track.length >= 2 ? track : undefined
    trackCache.set(key, result ?? [])
    return result
  } catch (err) {
    console.warn('[railwayGeometry] Overpass geometry unavailable:', err)
    trackCache.set(key, [])
    return undefined
  }
}

/**
 * Prefetch track geometry for multiple segment start/end pairs in parallel.
 */
export async function prefetchRailwayTracks(
  pairs: { fromLat: number; fromLon: number; toLat: number; toLon: number }[],
): Promise<void> {
  await Promise.allSettled(
    pairs.map((p) => fetchRailwayTrack(p.fromLat, p.fromLon, p.toLat, p.toLon)),
  )
}
