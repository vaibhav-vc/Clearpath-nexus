import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createMultimodalPlan,
  fetchIntegratedOperations,
  type MultimodalLegInput,
  type MultimodalPlan,
  type OperationsOverview,
  type ShipmentTwin,
} from '../services/api'

const emptyLeg = (origin = ''): MultimodalLegInput => ({
  mode: 'RAIL',
  origin,
  destination: '',
  distance_km: 0,
  estimated_minutes: 0,
  cost_amount: null,
  cost_source_type: 'UNAVAILABLE',
  risk_score: null,
  risk_source_type: 'UNAVAILABLE',
  compliance_status: 'NOT_ASSESSED',
  constraints: [],
})

function total(values: Record<string, number>) {
  return Object.values(values).reduce((sum, value) => sum + value, 0)
}

function StateBadge({ value }: { value: string }) {
  const danger = value.includes('BLOCK') || value === 'HOLD'
  const warning = value.includes('REVIEW') || value === 'WARNING'
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${danger ? 'border-rose-700 bg-rose-950 text-rose-300' : warning ? 'border-amber-700 bg-amber-950 text-amber-300' : 'border-cyan-700 bg-cyan-950 text-cyan-300'}`}>{value}</span>
}

export default function IntegratedOperations() {
  const [overview, setOverview] = useState<OperationsOverview | null>(null)
  const [twin, setTwin] = useState<ShipmentTwin[]>([])
  const [plans, setPlans] = useState<MultimodalPlan[]>([])
  const [name, setName] = useState('')
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [legs, setLegs] = useState<MultimodalLegInput[]>([emptyLeg()])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const result = await fetchIntegratedOperations()
      setOverview(result.overview)
      setTwin(result.twin)
      setPlans(result.plans)
      setError(null)
    } catch {
      setError('Integrated operations data is unavailable. No missing provider value has been substituted.')
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const setLeg = (index: number, patch: Partial<MultimodalLegInput>) => {
    setLegs((items) => items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }

  const submit = async () => {
    setSaving(true)
    setError(null)
    try {
      const prepared = legs.map((leg) => ({
        ...leg,
        cost_amount: leg.cost_amount ?? null,
        cost_source_type: leg.cost_amount !== null && leg.cost_amount !== undefined ? 'OPERATOR_INPUT' as const : 'UNAVAILABLE' as const,
        risk_score: leg.risk_score ?? null,
        risk_source_type: leg.risk_score == null ? 'UNAVAILABLE' as const : 'OPERATOR_INPUT' as const,
      }))
      const result = await createMultimodalPlan({ name, origin, destination, cost_currency: 'INR', legs: prepared })
      setPlans((items) => [result, ...items])
      setName('')
      setOrigin('')
      setDestination('')
      setLegs([emptyLeg()])
      await refresh()
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Plan evaluation failed'
      setError(`${message}. Check that every leg connects continuously from origin to destination.`)
    } finally {
      setSaving(false)
    }
  }

  const cards = useMemo(() => overview ? [
    ['ROUTES', overview.routes_total],
    ['SHIPMENTS', total(overview.shipments_by_status)],
    ['OPEN EVENTS', total(overview.open_events_by_severity)],
    ['COMPLIANCE CHECKS', total(overview.compliance_by_status)],
    ['MULTIMODAL PLANS', total(overview.multimodal_by_status)],
    ['TRAIN SYNCS', total(overview.train_sync_by_status)],
    ['PREDICTIONS', overview.prediction_count],
  ] : [], [overview])

  return <section className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-cyan-400">Version 6 integrated freight operations</p>
        <h2 className="mt-1 text-2xl font-bold text-white">Nexus Operations Fabric</h2>
        <p className="mt-1 max-w-4xl text-sm text-slate-400">One authenticated view across planning, live operations, tracking, predictive ETA, compliance, scheduling, multimodal evidence, audit, and analytics.</p>
      </div>
      <button onClick={() => void refresh()} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-cyan-500">Refresh fabric</button>
    </header>

    <div className="rounded-xl border border-amber-800/60 bg-amber-950/20 p-3 text-xs text-amber-200">Decision support only. This state projection is not signalling, ATP, interlocking, certified dispatch control, customs authority, or legal advice.</div>
    {error && <div className="rounded-xl border border-rose-800 bg-rose-950/30 p-3 text-sm text-rose-300">{error}</div>}

    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">{cards.map(([label, value]) => <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-900 p-4"><p className="text-[10px] font-bold text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold text-cyan-300">{value}</p></div>)}</div>

    <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="flex items-center justify-between"><div><h3 className="font-bold text-white">Multimodal plan evaluator</h3><p className="mt-1 text-xs text-slate-500">Factory → road → rail → port → vessel. Only values you enter are used.</p></div><StateBadge value="OPERATOR_INPUT" /></div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Plan name" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
          <input value={origin} onChange={(event) => { setOrigin(event.target.value); if (legs.length === 1 && !legs[0].origin) setLeg(0, { origin: event.target.value }) }} placeholder="Overall origin" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
          <input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="Overall destination" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
        </div>
        <div className="mt-4 space-y-3">{legs.map((leg, index) => <div key={index} className="rounded-xl border border-slate-800 bg-slate-950 p-3">
          <div className="mb-2 flex items-center justify-between"><span className="text-xs font-bold text-slate-300">LEG {index + 1}</span>{legs.length > 1 && <button onClick={() => setLegs((items) => items.filter((_, itemIndex) => itemIndex !== index))} className="text-xs text-rose-400">Remove</button>}</div>
          <div className="grid gap-2 md:grid-cols-4">
            <select value={leg.mode} onChange={(event) => setLeg(index, { mode: event.target.value as MultimodalLegInput['mode'] })} className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs"><option>ROAD</option><option>RAIL</option><option>PORT</option><option>SEA</option></select>
            <input value={leg.origin} onChange={(event) => setLeg(index, { origin: event.target.value })} placeholder="Leg origin" className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs" />
            <input value={leg.destination} onChange={(event) => setLeg(index, { destination: event.target.value })} placeholder="Leg destination" className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs" />
            <select value={leg.compliance_status} onChange={(event) => setLeg(index, { compliance_status: event.target.value as MultimodalLegInput['compliance_status'] })} className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs"><option>NOT_ASSESSED</option><option>MANUAL_REVIEW</option></select>
            <input type="number" min="0" value={leg.distance_km || ''} onChange={(event) => setLeg(index, { distance_km: Number(event.target.value) })} placeholder="Distance km" className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs" />
            <input type="number" min="0" value={leg.estimated_minutes || ''} onChange={(event) => setLeg(index, { estimated_minutes: Number(event.target.value) })} placeholder="ETA minutes" className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs" />
            <input type="number" min="0" value={leg.cost_amount ?? ''} onChange={(event) => setLeg(index, { cost_amount: event.target.value ? Number(event.target.value) : null })} placeholder="Operator cost INR (optional)" className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs" />
            <input type="number" min="0" max="100" value={leg.risk_score ?? ''} onChange={(event) => setLeg(index, { risk_score: event.target.value ? Number(event.target.value) : null })} placeholder="Risk 0–100 (optional)" className="rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs" />
          </div>
        </div>)}</div>
        <div className="mt-3 flex flex-wrap gap-2"><button onClick={() => setLegs((items) => [...items, emptyLeg(items.at(-1)?.destination ?? '')])} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">Add connected leg</button><button disabled={saving || !name || !origin || !destination} onClick={() => void submit()} className="rounded-lg bg-cyan-500 px-4 py-2 text-xs font-bold text-slate-950 disabled:opacity-40">{saving ? 'Evaluating…' : 'Evaluate & snapshot'}</button></div>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5"><h3 className="font-bold text-white">SourceLine coverage</h3>{overview ? <><p className="mt-4 text-4xl font-bold text-emerald-300">{overview.traceability.traced_records} / {overview.traceability.total_records}</p><p className="mt-1 text-sm text-slate-400">{overview.traceability.percent}% traced records</p><div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full bg-emerald-500" style={{ width: `${overview.traceability.percent}%` }} /></div><p className="mt-3 text-[11px] text-slate-500">{overview.traceability.basis}</p></> : <p className="mt-4 text-sm text-slate-500">Loading owned evidence…</p>}
        <h4 className="mt-6 text-xs font-bold uppercase tracking-wider text-slate-400">Shipment state projection</h4><div className="mt-2 space-y-2">{twin.map((shipment) => <div key={shipment.shipment_id} className="rounded-lg bg-slate-950 p-3"><div className="flex items-center justify-between"><span className="text-sm font-semibold text-white">{shipment.reference}</span><StateBadge value={shipment.status} /></div><p className="mt-1 text-[11px] text-slate-500">State source {shipment.state_source} · {shipment.open_event_count} open events</p></div>)}{twin.length === 0 && <p className="text-xs text-slate-500">No owned shipments. This is an empty state, not a fabricated twin.</p>}</div>
      </section>
    </div>

    <section className="rounded-xl border border-slate-800 bg-slate-900 p-5"><h3 className="font-bold text-white">Reproducible multimodal decisions</h3><div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{plans.map((plan) => <article key={plan.id} className="rounded-xl border border-slate-800 bg-slate-950 p-4"><div className="flex items-center justify-between gap-2"><h4 className="font-semibold text-white">{plan.name}</h4><StateBadge value={plan.recommendation} /></div><p className="mt-2 text-xs text-slate-400">{plan.origin} → {plan.destination}</p><p className="mt-2 text-[11px] text-slate-500">{plan.legs.length} legs · {plan.total_distance_km.toFixed(1)} km · {Math.round(plan.total_eta_minutes / 60)} h</p><p className="mt-1 text-[11px] text-slate-500">Cost {plan.total_cost == null ? 'UNAVAILABLE' : `${plan.cost_currency} ${plan.total_cost.toLocaleString()}`} · risk {plan.overall_risk_score ?? 'UNAVAILABLE'}</p><p className="mt-2 text-[11px] text-cyan-400">Traceability {plan.traceability_summary.traced_inputs} / {plan.traceability_summary.expected_inputs}</p></article>)}{plans.length === 0 && <p className="text-xs text-slate-500">No multimodal plans have been evaluated.</p>}</div></section>
  </section>
}
