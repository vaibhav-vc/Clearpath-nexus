import { useMemo, useState } from 'react'
import { Circle, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import type { EnvironmentalZone, MapCondition, SegmentPath, Station, TrackSegmentDetail, TrainPosition } from '../types/route'
import MapLegend from './MapLegend'

// Leaflet's default icon resolves its images by relative URL, which breaks under
// a bundler. Bind the bundled assets so station and train markers actually render.
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const DEFAULT_CENTER: [number, number] = [21.1458, 79.0882]

interface MapViewerProps {
  segments: SegmentPath[]
  stations?: Station[]
  environmentalZones?: EnvironmentalZone[]
  mapConditions?: MapCondition[]
  routeLabel?: string
  trainPosition?: TrainPosition
  liveWeatherUpdated?: Date | null
  trackDetails?: TrackSegmentDetail[]
}

function FitRoute({ points }: { points: [number, number][] }) {
  const map = useMap()
  useMemo(() => {
    if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [32, 32] })
  }, [map, points])
  return null
}

export default function MapViewer({
  segments,
  stations = [],
  environmentalZones = [],
  mapConditions = [],
  routeLabel,
  trainPosition,
  liveWeatherUpdated,
  trackDetails = [],
}: MapViewerProps) {
  const [legendCollapsed, setLegendCollapsed] = useState(false)
  const routePoints = segments.flatMap((segment) => segment.coordinates.map(([lat, lon]) => [lat, lon] as [number, number]))
  const points = routePoints.length ? routePoints : stations.map((station) => [station.lat, station.lon] as [number, number])

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-slate-700/60 shadow-2xl shadow-blue-950/60">
      <MapContainer center={DEFAULT_CENTER} zoom={6} className="h-full w-full" scrollWheelZoom>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitRoute points={points} />
        {segments.map((segment, index) => (
          <Polyline key={segment.id} positions={segment.coordinates.map(([lat, lon]) => [lat, lon] as [number, number])} pathOptions={{ color: segment.status === 'HARD_BLOCKED' ? '#ef4444' : index === 0 ? '#22d3ee' : '#60a5fa', weight: 5 }}>
            <Popup>{trackDetails[index]?.label ?? `Track segment ${index + 1}`}</Popup>
          </Polyline>
        ))}
        {stations.map((station) => <Marker key={station.id} position={[station.lat, station.lon]}><Popup>{station.name} ({station.code})</Popup></Marker>)}
        {trainPosition && <Marker position={[trainPosition.lat, trainPosition.lon]}><Popup>Current train position</Popup></Marker>}
        {environmentalZones.map((zone) => zone.coordinates.length > 0 && <Circle key={zone.id} center={[zone.coordinates[0][0], zone.coordinates[0][1]]} radius={12000} pathOptions={{ color: '#f59e0b' }} />)}
        {mapConditions.map((condition) => <Circle key={condition.id} center={[condition.lat, condition.lon]} radius={5000} pathOptions={{ color: '#fb923c', fillOpacity: 0.12 }} />)}
      </MapContainer>
      <div className={`absolute top-3 left-3 z-10 transition-all ${legendCollapsed ? 'w-11' : 'w-[215px]'}`}>
        <MapLegend routeLabel={routeLabel} conditionCount={mapConditions.length} liveWeatherUpdated={liveWeatherUpdated} collapsed={legendCollapsed} onToggle={() => setLegendCollapsed((value) => !value)} />
      </div>
    </div>
  )
}
