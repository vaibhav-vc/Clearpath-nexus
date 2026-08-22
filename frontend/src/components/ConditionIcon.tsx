import type { ConditionCategory, ConditionType } from '../maps/conditionSymbols'
import { CATEGORY_COLORS } from '../maps/conditionSymbols'

interface Props {
  type: ConditionType
  size?: number
  className?: string
}

function typeCategory(type: ConditionType): ConditionCategory {
  if (
    type === 'general_alert' ||
    type === 'storm_warning' ||
    type === 'flood_risk' ||
    type === 'landslide_risk' ||
    type === 'wildfire_risk' ||
    type === 'seismic_activity' ||
    type === 'hazmat_alert' ||
    type === 'air_pollution' ||
    type === 'debris_on_track' ||
    type === 'vegetation_risk'
  ) {
    return 'environmental'
  }
  if (
    type === 'all_clear' ||
    type === 'good_signal' ||
    type === 'weak_signal' ||
    type === 'no_signal' ||
    type === 'track_clear' ||
    type === 'track_caution' ||
    type === 'track_blocked' ||
    type === 'maintenance' ||
    type === 'station_active' ||
    type === 'port_active'
  ) {
    return 'operational'
  }
  return 'weather'
}

function svgInner(type: ConditionType): string {
  const cat = typeCategory(type)
  const stroke = CATEGORY_COLORS[cat].stroke

  switch (type) {
    case 'clear':
      return '<circle cx="12" cy="12" r="6" fill="#FBBF24" stroke="' + stroke + '" stroke-width="1"/>'
    case 'partly_cloudy':
      return '<circle cx="8" cy="10" r="4" fill="#FBBF24"/><ellipse cx="14" cy="14" rx="7" ry="4" fill="#E2E8F0" stroke="' + stroke + '" stroke-width="0.8"/>'
    case 'cloudy':
      return '<ellipse cx="10" cy="13" rx="6" ry="3.5" fill="#CBD5E1"/><ellipse cx="15" cy="11" rx="5" ry="3" fill="#94A3B8"/>'
    case 'fog':
    case 'mist':
      return '<ellipse cx="12" cy="10" rx="7" ry="3.5" fill="#94A3B8"/><line x1="4" y1="15" x2="20" y2="15" stroke="#64748B" stroke-width="1.5"/><line x1="5" y1="18" x2="19" y2="18" stroke="#64748B" stroke-width="1.5"/>'
    case 'light_rain':
    case 'heavy_rain':
      return '<ellipse cx="12" cy="9" rx="7" ry="3.5" fill="#64748B"/><line x1="8" y1="14" x2="7" y2="19" stroke="#38BDF8" stroke-width="1.5"/><line x1="12" y1="14" x2="11" y2="19" stroke="#38BDF8" stroke-width="1.5"/><line x1="16" y1="14" x2="15" y2="19" stroke="#38BDF8" stroke-width="1.5"/>'
    case 'thunderstorm':
    case 'storm_warning':
      return '<ellipse cx="12" cy="9" rx="7" ry="3.5" fill="#475569"/><polygon points="13,12 10,17 13,17 11,22" fill="#FBBF24"/>'
    case 'strong_wind':
    case 'high_winds':
    case 'dust':
      return '<path d="M4 10h12a3 3 0 100-6H8" fill="none" stroke="' + stroke + '" stroke-width="1.5"/><path d="M4 14h10a2.5 2.5 0 100-5H7" fill="none" stroke="' + stroke + '" stroke-width="1.5"/><path d="M4 18h8a2 2 0 100-4H6" fill="none" stroke="' + stroke + '" stroke-width="1.5"/>'
    case 'high_temp':
      return '<rect x="10" y="4" width="4" height="14" rx="2" fill="#EF4444"/><circle cx="12" cy="18" r="3" fill="#EF4444"/>'
    case 'low_temp':
      return '<rect x="10" y="4" width="4" height="14" rx="2" fill="#38BDF8"/><circle cx="12" cy="18" r="3" fill="#38BDF8"/>'
    case 'track_clear':
    case 'track_caution':
    case 'track_blocked': {
      const c = type === 'track_clear' ? '#22C55E' : type === 'track_caution' ? '#EAB308' : '#EF4444'
      const x = type === 'track_blocked' ? '<line x1="5" y1="5" x2="19" y2="19" stroke="#EF4444" stroke-width="2"/>' : ''
      return (
        '<line x1="6" y1="8" x2="6" y2="18" stroke="' +
        c +
        '" stroke-width="2"/><line x1="18" y1="8" x2="18" y2="18" stroke="' +
        c +
        '" stroke-width="2"/><line x1="4" y1="12" x2="20" y2="12" stroke="#64748B" stroke-width="1.5"/>' +
        x
      )
    }
    case 'all_clear':
      return '<circle cx="12" cy="12" r="9" fill="#22C55E"/><path d="M8 12l3 3 5-6" fill="none" stroke="#fff" stroke-width="2"/>'
    case 'general_alert':
      return '<polygon points="12,3 22,21 2,21" fill="#F97316"/><line x1="12" y1="9" x2="12" y2="14" stroke="#000" stroke-width="2"/><circle cx="12" cy="17" r="1" fill="#000"/>'
    case 'flood_risk':
      return '<rect x="8" y="8" width="8" height="6" fill="#38BDF8"/><path d="M4 18 Q8 14 12 18 T20 18" fill="none" stroke="#2563EB" stroke-width="2"/>'
    case 'wildfire_risk':
      return '<path d="M12 4c0 4-4 5-4 9a4 4 0 008 0c0-4-4-5-4-9z" fill="#F97316"/>'
    case 'station_active':
      return '<rect x="6" y="10" width="12" height="10" fill="#38BDF8"/><polygon points="12,4 18,10 6,10" fill="#2563EB"/>'
    case 'port_active':
      return '<path d="M12 5v12M8 9l4-4 4 4" stroke="#38BDF8" stroke-width="2" fill="none"/><path d="M6 19h12" stroke="#64748B" stroke-width="2"/>'
    default:
      return (
        '<circle cx="12" cy="12" r="8" fill="' +
        CATEGORY_COLORS[cat].fill.replace('0.2', '0.6') +
        '" stroke="' +
        stroke +
        '" stroke-width="1.5"/>'
      )
  }
}

export default function ConditionIcon({ type, size = 22, className = '' }: Props) {
  const cat = typeCategory(type)
  const border = CATEGORY_COLORS[cat].stroke

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md border bg-slate-950/90 ${className}`}
      style={{ width: size + 6, height: size + 6, borderColor: border }}
      aria-hidden
    >
      {/* svgInner only accepts the closed ConditionType enum; no user-controlled markup reaches this sink. */}
      <svg width={size} height={size} viewBox="0 0 24 24" dangerouslySetInnerHTML={{ __html: svgInner(type) }} />
    </span>
  )
}
