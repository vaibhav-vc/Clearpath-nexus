export interface CargoDimensions {
  height: number
  width: number
  weight: number
}

export type LocationMode = 'station' | 'coordinates' | 'live'

export interface TrainLocationInput {
  mode: LocationMode
  station_code?: string
  lat?: number
  lon?: number
}

export type SegmentPhase = 'TRAVERSED' | 'CURRENT' | 'UPCOMING'

export interface SegmentPath {
  id: string
  status: 'APPROVED' | 'HARD_BLOCKED'
  coordinates: [number, number][]
  phase?: SegmentPhase
  label?: string
}

export interface TrackSegmentDetail {
  id: string
  label: string
  phase: SegmentPhase
  distance_km: number
  progress_pct?: number
  max_height: number
  max_width: number
  max_weight: number
  congestion: number
  historical_delay_hours: number
  clearance_status: 'APPROVED' | 'HARD_BLOCKED'
  advisory?: string
}

export interface AlternateRoute {
  label: string
  reliability_score: number
  segment_ids: string[]
  estimated_hours?: number
  weather_score?: number
}

export interface TrainPosition {
  lat: number
  lon: number
  mode: LocationMode
  snapped_track?: string
  offset_km?: number
  station_code?: string
}

export interface ScoreBreakdown {
  weather: number
  port: number
  congestion: number
  historical: number
}

export interface ProvenanceSummary {
  decision_record_id: string
  traceability: { traced: number; total: number; coverage_pct: number }
  freshness: Record<string, number>
  source_modes: Record<string, number>
  decision_use: Record<string, number>
  warnings: string[]
}

export interface SourceBrief {
  id: string
  key: string
  label: string
  category: string
  authority_level: string
  official: boolean
  free_for_mvp: boolean
  requires_key: boolean
  reference_url?: string
  license_name?: string
  attribution_text?: string
  limitations: Record<string, unknown>
  freshness_policy: Record<string, number | null>
  current_status?: Record<string, unknown>
}

export interface ProvenanceRecord {
  id: string
  entity_type: string
  decision_input_role?: string
  canonical_source_type: string
  raw_source_state?: string
  source?: SourceBrief
  observed_at?: string
  fetched_at: string
  freshness: { state: string; age_seconds?: number }
  used_in_decision: boolean
  excluded_reason?: string
  transform: Record<string, string | null>
  value_summary: Record<string, unknown>
  decision_impact: Record<string, unknown>
}

export interface RouteEvidence {
  route: Record<string, unknown>
  snapshot: Record<string, unknown>
  traceability: ProvenanceSummary
  components: Array<{ role: string; label: string; status: string; record_ids: string[]; explanation: string }>
  records: ProvenanceRecord[]
  edges: Array<{ id: string; parent_record_id: string; child_record_id: string; relationship: string }>
  warnings: string[]
}

export interface ComplianceCheck {
  id: string
  route_id: string
  overall_status: string
  rule_pack_version: string
  disclaimer: string
  overridden: boolean
  override_reason?: string
  overridden_by?: string
  overridden_at?: string
  created_at: string
  documents: Array<{
    id: string
    document_type: string
    document_number?: string
    issuing_authority?: string
    issued_at?: string
    expires_at?: string
    checksum?: string
    verification_state: string
  }>
  overrides: Array<{ id: string; user_id: string; reason: string; created_at: string }>
  items: Array<{
    id: string
    rule_key: string
    rule_version: string
    status: string
    explanation: string
    recommended_action: string
    penalty_exposure?: string
    evidence: Record<string, unknown>
    rule_source: Record<string, unknown>
  }>
}

export interface RouteEvaluateResponse {
  route_id: string
  status: 'APPROVED' | 'HARD_BLOCKED'
  reliability_score: number
  blocking_segment_id?: string
  estimated_hours?: number
  score_breakdown?: ScoreBreakdown
  segments: SegmentPath[]
  environmental_alerts: string[]
  provenance_summary?: ProvenanceSummary
}

export interface RouteSuggestResponse extends RouteEvaluateResponse {
  train_position: TrainPosition
  remaining_km: number
  eta_hours?: number
  track_details: TrackSegmentDetail[]
  alternate_routes: AlternateRoute[]
  next_station?: string
}

export interface Station {
  id: string
  name: string
  code: string
  lat: number
  lon: number
}

export interface ThreatSimulationResponse {
  original_score: number
  simulated_score: number
  degradation_pct: number
  alerts: string[]
}

import type { ConditionCategory, ConditionType } from '../maps/conditionSymbols'

export interface EnvironmentalZone {
  id: string
  type: ConditionType | 'storm' | 'dust' | 'solar' | 'fog' | 'cloud'
  coordinates: [number, number][]
}

export interface MapCondition {
  id: string
  type: ConditionType
  category: ConditionCategory
  lat: number
  lon: number
  reading?: string
  detail?: string
}

export interface OperatorLoadingWindow {
  start_time: string
  end_time: string
}

export interface RouteHistoryItem {
  id: string
  source_station_code: string
  dest_station_code: string
  cargo_height_requested: number
  cargo_width_requested: number
  cargo_weight_requested: number
  status: 'APPROVED' | 'HARD_BLOCKED'
  dispatch_status: 'DRAFT' | 'DISPATCHED'
  reliability_score: number
  estimated_hours?: number
  dispatched_at?: string
  created_at: string
}

export interface TrainSchedule {
  id: string
  generated_route_id?: string
  train_code: string
  train_name: string
  source_station_code: string
  dest_station_code: string
  scheduled_departure: string
  scheduled_arrival: string
  berth_window_start?: string
  berth_window_end?: string
  schedule_status: 'PLANNED' | 'READY' | 'DISPATCHED' | 'CANCELLED'
  conflict_status: 'CLEAR' | 'WARNING' | 'BLOCKED'
  conflict_reason?: string
  is_demo: boolean
  dispatched_at?: string
  created_at: string
  updated_at: string
}
