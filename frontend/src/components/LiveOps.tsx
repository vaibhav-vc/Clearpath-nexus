import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchLiveOps,
  updateLiveEvent,
  type LiveObservation,
  type LiveOpsEvent,
  type ModelSummary,
  type ProviderRuntimeHealth,
  type ShipmentSummary,
} from '../services/api'

const trustStyle: Record<string, string> = {
  LIVE: 'bg-emerald-950 text-emerald-300 border-emerald-700',
  FRESH: 'bg-emerald-950 text-emerald-300 border-emerald-700',
  CACHED: 'bg-cyan-950 text-cyan-300 border-cyan-700',
  AGING: 'bg-amber-950 text-amber-300 border-amber-700',
  STALE: 'bg-orange-950 text-orange-300 border-orange-700',
  UNAVAILABLE: 'bg-rose-950 text-rose-300 border-rose-700',
  INVALID: 'bg-rose-950 text-rose-300 border-rose-700',
  OPERATOR_INPUT: 'bg-violet-950 text-violet-300 border-violet-700',
  SIMULATED: 'bg-fuchsia-950 text-fuchsia-300 border-fuchsia-700',
}

function TrustBadge({ value }: { value: string }) {
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${trustStyle[value] ?? 'border-slate-700 bg-slate-900 text-slate-300'}`}>{value}</span>
}

function ageLabel(value?: string | null) {
  if (!value) return 'No timestamp'
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

export default function LiveOps() {
  const [events, setEvents] = useState<LiveOpsEvent[]>([])
  const [observations, setObservations] = useState<LiveObservation[]>([])
  const [providers, setProviders] = useState<ProviderRuntimeHealth[]>([])
  const [shipments, setShipments] = useState<ShipmentSummary[]>([])
  const [models, setModels] = useState<ModelSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await fetchLiveOps()
      setEvents(result.events)
      setObservations(result.observations)
      setProviders(result.providers)
      setShipments(result.shipments)
      setModels(result.models)
      setUpdatedAt(new Date())
      setError(null)
    } catch {
      setError('LiveOps data is unavailable. Existing route planning remains available with truthful provider fallbacks.')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const interval = window.setInterval(() => void refresh(), 15_000)
    return () => window.clearInterval(interval)
  }, [refresh])

  const openEvents = useMemo(() => events.filter((event) => event.state === 'OPEN'), [events])
  const atRisk = useMemo(() => openEvents.filter((event) => ['HIGH', 'CRITICAL'].includes(event.severity)), [openEvents])

  const acknowledge = async (event: LiveOpsEvent) => {
    const updated = await updateLiveEvent(event.id, 'ACKNOWLEDGED')
    setEvents((items) => items.map((item) => item.id === updated.id ? updated : item))
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-400">Live Operations Control Center</p>
          <h2 className="mt-1 text-2xl font-bold text-white">LiveOps</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Validated provider observations, operational events, shipment tracking, and model readiness. Every state shown below comes from persisted evidence.</p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <button onClick={() => void refresh()} className="rounded-lg border border-slate-700 px-3 py-2 text-slate-300 hover:border-cyan-500">Refresh</button>
          <p className="mt-1">{updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : 'Waiting for first refresh'}</p>
        </div>
      </div>

      {error && <p className="rounded-xl border border-rose-900 bg-rose-950/30 p-3 text-sm text-rose-300">{error}</p>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['ACTIVE SHIPMENTS', shipments.length, 'text-cyan-300'],
          ['OPEN EVENTS', openEvents.length, 'text-amber-300'],
          ['AT RISK', atRisk.length, 'text-rose-300'],
          ['PROVIDERS', providers.length, 'text-emerald-300'],
        ].map(([label, value, color]) => <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-900 p-4"><p className="text-[10px] font-bold tracking-wider text-slate-500">{label}</p><p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p></div>)}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300">Operational events</h3>
          {events.length === 0 && <p className="rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-500">No persisted operational events. This does not mean conditions are clear when providers are unavailable.</p>}
          {events.slice(0, 20).map((event) => <article key={event.id} className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><TrustBadge value={event.severity} /><h4 className="font-semibold text-white">{event.title}</h4></div><span className="text-xs text-slate-500">{ageLabel(event.observed_at)}</span></div><p className="mt-2 text-sm text-slate-400">{event.detail}</p><div className="mt-3 flex items-center justify-between"><TrustBadge value={event.state} />{event.state === 'OPEN' && event.actionable && <button onClick={() => void acknowledge(event)} className="rounded-lg bg-cyan-500 px-3 py-1.5 text-xs font-bold text-slate-950">Acknowledge</button>}</div></article>)}
        </div>

        <div className="space-y-5">
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-4"><h3 className="text-sm font-bold text-white">Provider health</h3><div className="mt-3 space-y-3">{providers.length === 0 && <p className="text-xs text-slate-500">The ingestor has not persisted provider runtime state yet.</p>}{providers.map((provider) => <div key={provider.provider_key} className="rounded-lg bg-slate-950 p-3"><div className="flex items-center justify-between"><span className="font-mono text-xs text-cyan-300">{provider.provider_key}</span><TrustBadge value={provider.freshness} /></div><p className="mt-1 text-[11px] text-slate-500">Circuit {provider.circuit_state} · {provider.consecutive_failures} consecutive failures · {provider.latency_ms == null ? 'no latency sample' : `${provider.latency_ms} ms`}</p></div>)}</div></section>
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-4"><h3 className="text-sm font-bold text-white">Delay model registry</h3><div className="mt-3 space-y-3">{models.length === 0 && <p className="text-xs text-slate-500">No trained model artifact is registered. Deterministic ETA remains active.</p>}{models.map((model) => <div key={`${model.model_name}-${model.version}`} className="rounded-lg bg-slate-950 p-3"><div className="flex items-center justify-between"><span className="font-mono text-xs text-violet-300">{model.model_name} {model.version}</span><TrustBadge value={model.status} /></div><p className="mt-1 text-[11px] text-slate-500">{model.algorithm} · schema {model.feature_schema_version}</p><p className="mt-1 font-mono text-[9px] text-slate-600">SHA-256 {model.artifact_checksum.slice(0, 16)}…</p>{!model.production && <p className="mt-2 text-[11px] text-amber-300">Advisory candidate only; deterministic prediction remains operational.</p>}</div>)}</div></section>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-4"><h3 className="text-sm font-bold text-white">Latest persisted observations</h3><div className="mt-3 space-y-2">{observations.slice(0, 12).map((observation) => <div key={observation.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-950 p-3"><div><p className="font-mono text-xs text-cyan-300">{observation.provider_key} · {observation.entity_id ?? observation.observation_type}</p><p className="mt-1 text-[11px] text-slate-500">Observed {ageLabel(observation.observed_at)} · fetched {ageLabel(observation.fetched_at)}</p></div><TrustBadge value={observation.valid ? observation.freshness : 'INVALID'} /></div>)}{observations.length === 0 && <p className="text-xs text-slate-500">No observations have been ingested.</p>}</div></section>
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-4"><h3 className="text-sm font-bold text-white">Tracked shipments</h3><p className="mt-1 text-xs text-slate-500">Location sharing is shipment-specific, explicit, and stoppable.</p><div className="mt-3 space-y-2">{shipments.map((shipment) => <div key={shipment.id} className="rounded-lg bg-slate-950 p-3"><div className="flex items-center justify-between"><span className="font-semibold text-white">{shipment.reference}</span><TrustBadge value={shipment.latest_position?.freshness ?? (shipment.tracking_enabled ? 'UNAVAILABLE' : 'OFFLINE')} /></div><p className="mt-1 text-[11px] text-slate-500">{shipment.tracking_enabled ? 'Tracking enabled by operator' : 'Tracking stopped'} · source {shipment.latest_position?.source_type ?? 'UNAVAILABLE'}</p></div>)}{shipments.length === 0 && <p className="text-xs text-slate-500">No shipments are registered for this operator.</p>}</div></section>
      </div>
    </section>
  )
}
