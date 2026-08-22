import axios from 'axios'
import type { ComplianceState, CostSourceType, MultimodalSourceType } from '../types/status'
import type {
  RouteEvaluateResponse,
  RouteSuggestResponse,
  Station,
  ThreatSimulationResponse,
  TrainLocationInput,
  OperatorLoadingWindow,
  RouteHistoryItem,
  TrainSchedule,
  RouteEvidence,
  SourceBrief,
  ComplianceCheck,
} from '../types/route'
import { getAccessToken } from './supabaseClient'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

// The backend requires a valid Supabase bearer token on every /planner and
// /port route (see backend/app/core/security.py). Attach it here, once, so
// every call site below stays token-free. A missing/expired session comes
// back from the backend as a 401 rather than silently going through.
api.interceptors.request.use(async (config) => {
  const token = await getAccessToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export async function fetchStations(): Promise<Station[]> {
  const { data } = await api.get<Station[]>('/planner/stations')
  return data
}

export async function suggestRoute(payload: {
  cargo: { height: number; width: number; weight: number }
  destination_code: string
  location: TrainLocationInput
  train_arrival_hours: number
  loading_window?: OperatorLoadingWindow
}): Promise<RouteSuggestResponse> {
  const { data } = await api.post<RouteSuggestResponse>('/planner/suggest', payload, { timeout: 30000 })
  return data
}

export async function evaluateRoute(payload: {
  cargo: { height: number; width: number; weight: number }
  source_code: string
  dest_code: string
  train_arrival_hours: number
  loading_window?: OperatorLoadingWindow
}): Promise<RouteEvaluateResponse> {
  const { data } = await api.post<RouteEvaluateResponse>('/planner/evaluate', payload, { timeout: 30000 })
  return data
}

export async function simulateThreat(payload: {
  storm_severity: number
  solar_kp_index: number
  port_congestion: number
}): Promise<ThreatSimulationResponse> {
  const { data } = await api.post<ThreatSimulationResponse>('/planner/simulate', payload)
  return data
}

export async function fetchMapConditions(payload: {
  points: { lat: number; lon: number; id?: string }[]
  destination_code?: string
}) {
  const { data } = await api.post('/weather/map-conditions', payload)
  return data
}

export async function fetchRouteWeatherPoints(payload: {
  points: { id: string; lat: number; lon: number }[]
}) {
  const { data } = await api.post('/weather/route-points', payload)
  return data
}

export async function fetchBackendTrackGeometry(bbox: {
  minLat: number; minLon: number; maxLat: number; maxLon: number
}) {
  const { data } = await api.get('/geometry/track', { params: {
    min_lat: bbox.minLat, min_lon: bbox.minLon, max_lat: bbox.maxLat, max_lon: bbox.maxLon,
  } })
  return data
}

export interface LiveCorridorTrain {
  train_number: string
  train_name: string
  status: string
  delay_minutes: number | null
}

export interface LiveCorridorTrafficResponse {
  available: boolean
  provider: string
  source_code?: string
  dest_code?: string
  trains: LiveCorridorTrain[]
  alerts: string[]
  message?: string
}

export async function fetchLiveCorridorTraffic(sourceCode: string, destCode: string): Promise<LiveCorridorTrafficResponse> {
  const { data } = await api.get<LiveCorridorTrafficResponse>('/railways/live-corridor-traffic', {
    params: { source_code: sourceCode, dest_code: destCode },
  })
  return data
}


export async function fetchRouteHistory(): Promise<RouteHistoryItem[]> {
  const { data } = await api.get<RouteHistoryItem[]>('/planner/routes')
  return data
}

export async function fetchRouteEvidence(routeId: string): Promise<RouteEvidence> {
  const { data } = await api.get<RouteEvidence>(`/provenance/routes/${routeId}`)
  return data
}

export async function fetchSources(): Promise<SourceBrief[]> {
  const { data } = await api.get<{ items: SourceBrief[] }>('/provenance/sources')
  return data.items
}

export interface ComplianceDocumentInput {
  document_type: string
  document_number?: string
  issuing_authority?: string
  expires_at?: string
  verification_state: 'UNVERIFIED' | 'OPERATOR_DECLARED' | 'VERIFIED'
}

export async function runComplianceCheck(
  routeId: string,
  payload: {
    documents: ComplianceDocumentInput[]
    cargo_declaration_complete: boolean
    human_approval_obtained: boolean
    transporter_reference?: string
    shipment_reference?: string
    eway_bill_reference?: string
    port_customs_reference?: string
  },
): Promise<ComplianceCheck> {
  const { data } = await api.post<ComplianceCheck>(`/compliance/routes/${routeId}/checks`, payload)
  return data
}

export async function dispatchRoute(routeId: string): Promise<{ route_id: string; dispatch_status: string; dispatched_at: string }> {
  const { data } = await api.post(`/planner/routes/${routeId}/dispatch`)
  return data
}

export async function fetchSchedules(): Promise<TrainSchedule[]> {
  const { data } = await api.get<TrainSchedule[]>('/planner/schedules')
  return data
}

export async function dispatchSchedule(scheduleId: string): Promise<TrainSchedule> {
  const { data } = await api.post<TrainSchedule>(`/planner/schedules/${scheduleId}/dispatch`)
  return data
}

export async function updateSchedule(
  scheduleId: string,
  patch: Partial<Pick<TrainSchedule, 'scheduled_departure' | 'scheduled_arrival' | 'berth_window_start' | 'berth_window_end' | 'schedule_status'>>,
): Promise<TrainSchedule> {
  const { data } = await api.patch<TrainSchedule>(`/planner/schedules/${scheduleId}`, patch)
  return data
}

export interface TrainSyncState {
  schedule_id: string
  provider_key: string
  train_number: string
  status: string
  freshness: string
  current_station?: string | null
  station_code?: string | null
  delay_minutes?: number | null
  observed_at?: string | null
  fetched_at: string
  provenance_record_id?: string | null
  last_error?: string | null
  authority_notice: string
}

export async function synchronizeTrainSchedule(scheduleId: string): Promise<TrainSyncState> {
  const { data } = await api.post<TrainSyncState>(`/live/train-sync/schedules/${scheduleId}`)
  return data
}

export interface LiveOpsEvent {
  id: string
  event_type: string
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  state: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED'
  title: string
  detail: string
  route_id?: string | null
  shipment_id?: string | null
  observed_at: string
  created_at: string
  source_observation_id?: string | null
  actionable: boolean
}

export interface LiveObservation {
  id: string
  provider_key: string
  observation_type: string
  entity_id?: string | null
  status: string
  freshness: string
  observed_at?: string | null
  fetched_at: string
  valid: boolean
  data: Record<string, unknown>
}

export interface ProviderRuntimeHealth {
  provider_key: string
  circuit_state: string
  consecutive_failures: number
  last_success_at?: string | null
  last_failure_at?: string | null
  latency_ms?: number | null
  freshness: string
  rate_limited: boolean
  authentication_state: string
}

export interface ShipmentSummary {
  id: string
  reference: string
  route_id?: string | null
  status: string
  tracking_enabled: boolean
  latest_position?: {
    latitude: number
    longitude: number
    speed?: number | null
    observed_at: string
    freshness: string
    source_type: string
  } | null
}

export interface ModelSummary {
  model_name: string
  version: string
  status: string
  production: boolean
  algorithm: string
  artifact_checksum: string
  feature_schema_version: string
  metrics: Record<string, unknown>
  eligibility: Record<string, unknown>
}

export async function fetchLiveOps(): Promise<{
  events: LiveOpsEvent[]
  observations: LiveObservation[]
  providers: ProviderRuntimeHealth[]
  shipments: ShipmentSummary[]
  models: ModelSummary[]
}> {
  const [events, observations, providers, shipments, models] = await Promise.all([
    api.get<LiveOpsEvent[]>('/live/events'),
    api.get<{ items: LiveObservation[] }>('/live/observations'),
    api.get<{ items: ProviderRuntimeHealth[] }>('/live/provider-health'),
    api.get<{ items: ShipmentSummary[] }>('/live/shipments'),
    api.get<ModelSummary[]>('/models'),
  ])
  return {
    events: events.data,
    observations: observations.data.items,
    providers: providers.data.items,
    shipments: shipments.data.items,
    models: models.data,
  }
}

export async function updateLiveEvent(
  eventId: string,
  state: 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED',
): Promise<LiveOpsEvent> {
  const { data } = await api.patch<LiveOpsEvent>(`/live/events/${eventId}`, { state })
  return data
}

export interface OperationsOverview {
  generated_at: string
  product_version: string
  routes_total: number
  shipments_by_status: Record<string, number>
  schedules_by_status: Record<string, number>
  open_events_by_severity: Record<string, number>
  compliance_by_status: Record<string, number>
  multimodal_by_status: Record<string, number>
  train_sync_by_status: Record<string, number>
  prediction_count: number
  traceability: { traced_records: number; total_records: number; percent: number; basis: string }
  provider_health: Array<Record<string, unknown>>
  notices: string[]
}

export interface ShipmentTwin {
  shipment_id: string
  reference: string
  status: string
  tracking_enabled: boolean
  route_id?: string | null
  latest_position?: Record<string, unknown> | null
  open_event_count: number
  state_source: string
}

export interface MultimodalLegInput {
  mode: 'ROAD' | 'RAIL' | 'PORT' | 'SEA'
  origin: string
  destination: string
  distance_km: number
  estimated_minutes: number
  cost_amount?: number | null
  cost_source_type: CostSourceType
  risk_score?: number | null
  // Narrower than CanonicalSourceType on purpose: this is a request payload and
  // the backend rejects OFFLINE_COMPUTED / IMPORTED_DOCUMENT with a 422.
  risk_source_type: MultimodalSourceType
  compliance_status: ComplianceState
  compliance_check_id?: string | null
  source_provider?: string | null
  source_dataset?: string | null
  source_reference?: string | null
  source_observed_at?: string | null
  constraints: Array<{ name: string; status: string; detail: string }>
}

export interface MultimodalPlan {
  id: string
  name: string
  origin: string
  destination: string
  status: string
  recommendation: string
  total_distance_km: number
  total_eta_minutes: number
  total_cost?: number | null
  cost_currency: string
  cost_completeness: number
  overall_risk_score?: number | null
  compliance_status: string
  traceability_summary: Record<string, number | string>
  created_at: string
  legs: Array<MultimodalLegInput & { id: string; sequence: number; provenance_record_id?: string | null }>
}

export async function fetchIntegratedOperations(): Promise<{
  overview: OperationsOverview
  twin: ShipmentTwin[]
  plans: MultimodalPlan[]
}> {
  const [overview, twin, plans] = await Promise.all([
    api.get<OperationsOverview>('/operations/overview'),
    api.get<{ shipments: ShipmentTwin[] }>('/operations/twin'),
    api.get<MultimodalPlan[]>('/multimodal/plans'),
  ])
  return { overview: overview.data, twin: twin.data.shipments, plans: plans.data }
}

export async function createMultimodalPlan(payload: {
  name: string
  origin: string
  destination: string
  cost_currency: string
  legs: MultimodalLegInput[]
}): Promise<MultimodalPlan> {
  const { data } = await api.post<MultimodalPlan>('/multimodal/plans', payload)
  return data
}
