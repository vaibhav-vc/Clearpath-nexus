/**
 * Deployment-tunable frontend values.
 *
 * These were literals scattered across components -- a default corridor of
 * NGP -> JNPT repeated in three panels, a map centred on Nagpur, a refresh
 * cadence buried in a setInterval call. None of that is wrong, but none of it
 * belonged to the component that happened to render it, and a deployment
 * covering a different network had to edit JSX to move the map.
 *
 * Every value falls back to its previous literal, so an unconfigured build
 * behaves exactly as before.
 */

function envString(value: string | undefined, fallback: string): string {
  const trimmed = value?.trim()
  return trimmed ? trimmed : fallback
}

function envNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

/** Corridor pre-selected in the planner and the live-traffic panels. */
export const DEFAULT_ORIGIN_CODE = envString(import.meta.env.VITE_DEFAULT_ORIGIN, 'NGP')
export const DEFAULT_DESTINATION_CODE = envString(
  import.meta.env.VITE_DEFAULT_DESTINATION,
  'JNPT',
)

/** Opening map view, used until a route or station set defines its own bounds. */
export const MAP_DEFAULT_CENTER: [number, number] = [
  envNumber(import.meta.env.VITE_MAP_CENTER_LAT, 21.1458),
  envNumber(import.meta.env.VITE_MAP_CENTER_LON, 79.0882),
]
export const MAP_DEFAULT_ZOOM = envNumber(import.meta.env.VITE_MAP_DEFAULT_ZOOM, 6)

/** Overlay circle radii in metres. */
export const MAP_ENVIRONMENTAL_ZONE_RADIUS_M = envNumber(
  import.meta.env.VITE_MAP_ZONE_RADIUS_M,
  12000,
)
export const MAP_CONDITION_RADIUS_M = envNumber(
  import.meta.env.VITE_MAP_CONDITION_RADIUS_M,
  5000,
)

/** How often the LiveOps control center re-polls the backend, in milliseconds. */
export const LIVEOPS_REFRESH_MS = envNumber(import.meta.env.VITE_LIVEOPS_REFRESH_MS, 15_000)
