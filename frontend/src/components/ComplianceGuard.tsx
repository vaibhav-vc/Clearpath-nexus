import { useEffect, useState } from 'react'
import { fetchRouteHistory, runComplianceCheck } from '../services/api'
import type { ComplianceCheck, RouteHistoryItem } from '../types/route'

export default function ComplianceGuard() {
  const [routes, setRoutes] = useState<RouteHistoryItem[]>([])
  const [routeId, setRouteId] = useState('')
  const [permitExpiry, setPermitExpiry] = useState('')
  const [permitNumber, setPermitNumber] = useState('')
  const [insuranceNumber, setInsuranceNumber] = useState('')
  const [declarationNumber, setDeclarationNumber] = useState('')
  const [transporterReference, setTransporterReference] = useState('')
  const [shipmentReference, setShipmentReference] = useState('')
  const [ewayBillReference, setEwayBillReference] = useState('')
  const [portCustomsReference, setPortCustomsReference] = useState('')
  const [cargoComplete, setCargoComplete] = useState(false)
  const [approved, setApproved] = useState(false)
  const [result, setResult] = useState<ComplianceCheck | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchRouteHistory().then((items) => { setRoutes(items); setRouteId(items[0]?.id ?? '') }).catch(() => setError('Route history is unavailable.'))
  }, [])

  const run = async () => {
    if (!routeId) return
    setError(null)
    try {
      const expiry = permitExpiry ? new Date(permitExpiry).toISOString() : undefined
      const documents = [
        permitNumber.trim() ? { document_type: 'PERMIT', document_number: permitNumber.trim(), expires_at: expiry, verification_state: 'OPERATOR_DECLARED' as const } : null,
        insuranceNumber.trim() ? { document_type: 'INSURANCE', document_number: insuranceNumber.trim(), verification_state: 'OPERATOR_DECLARED' as const } : null,
        declarationNumber.trim() ? { document_type: 'CARGO_DECLARATION', document_number: declarationNumber.trim(), verification_state: 'OPERATOR_DECLARED' as const } : null,
      ].filter((document): document is NonNullable<typeof document> => document !== null)
      setResult(await runComplianceCheck(routeId, {
        documents,
        cargo_declaration_complete: cargoComplete,
        human_approval_obtained: approved,
        transporter_reference: transporterReference.trim() || undefined,
        shipment_reference: shipmentReference.trim() || undefined,
        eway_bill_reference: ewayBillReference.trim() || undefined,
        port_customs_reference: portCustomsReference.trim() || undefined,
      }))
    } catch {
      setError('Compliance check failed. Verify the route and migrated database.')
    }
  }

  return (
    <section className="grid gap-5 lg:grid-cols-[360px_1fr]">
      <div className="h-fit rounded-2xl border border-slate-800 bg-slate-900 p-5">
        <p className="text-xs font-mono uppercase tracking-wider text-amber-300">Nexus ComplianceGuard</p>
        <h2 className="mt-2 text-xl font-bold">Pre-dispatch review</h2>
        <p className="mt-2 text-xs text-slate-400">Deterministic metadata checks. This does not provide legal advice or declare regulatory compliance.</p>
        <label className="mt-5 block text-xs text-slate-400">Stored route</label>
        <select value={routeId} onChange={(event) => setRouteId(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm">
          {routes.map((route) => <option key={route.id} value={route.id}>{route.source_station_code} → {route.dest_station_code} · {route.status}</option>)}
        </select>
        <label className="mt-4 block text-xs text-slate-400">Declared permit expiry</label>
        <input type="datetime-local" value={permitExpiry} onChange={(event) => setPermitExpiry(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
        <label className="mt-4 block text-xs text-slate-400">Permit reference</label>
        <input value={permitNumber} onChange={(event) => setPermitNumber(event.target.value)} placeholder="Operator-declared permit number" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
        <label className="mt-3 block text-xs text-slate-400">Insurance reference</label>
        <input value={insuranceNumber} onChange={(event) => setInsuranceNumber(event.target.value)} placeholder="Policy/reference number" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
        <label className="mt-3 block text-xs text-slate-400">Cargo declaration reference</label>
        <input value={declarationNumber} onChange={(event) => setDeclarationNumber(event.target.value)} placeholder="Declaration number" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm" />
        <div className="mt-4 grid grid-cols-2 gap-2">
          <input value={transporterReference} onChange={(event) => setTransporterReference(event.target.value)} placeholder="Transporter ref" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs" />
          <input value={shipmentReference} onChange={(event) => setShipmentReference(event.target.value)} placeholder="Shipment ref" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs" />
          <input value={ewayBillReference} onChange={(event) => setEwayBillReference(event.target.value)} placeholder="E-Way Bill ref" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs" />
          <input value={portCustomsReference} onChange={(event) => setPortCustomsReference(event.target.value)} placeholder="Port/customs ref" className="rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs" />
        </div>
        <label className="mt-4 flex gap-2 text-xs text-slate-300"><input type="checkbox" checked={cargoComplete} onChange={(event) => setCargoComplete(event.target.checked)} /> Cargo declaration reviewed</label>
        <label className="mt-3 flex gap-2 text-xs text-slate-300"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /> Human approval obtained</label>
        <button onClick={() => void run()} disabled={!routeId} className="mt-5 w-full rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-bold text-slate-950 disabled:opacity-40">Run compliance check</button>
        {error ? <p className="mt-3 text-xs text-rose-300">{error}</p> : null}
      </div>
      <div className="space-y-4">
        {!result ? <div className="rounded-2xl border border-dashed border-slate-700 p-10 text-center text-sm text-slate-500">Select a route and run a review.</div> : (
          <>
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5"><p className="text-xs text-slate-500">Overall decision-support state</p><p className="mt-1 text-2xl font-bold text-amber-300">{result.overall_status}</p><p className="mt-3 text-xs text-slate-400">{result.disclaimer}</p></div>
            {result.items.map((item) => <article key={item.id} className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="flex justify-between gap-3"><h3 className="font-semibold text-white">{item.rule_key.replaceAll('_', ' ')}</h3><span className="text-xs font-bold text-cyan-300">{item.status}</span></div><p className="mt-2 text-sm text-slate-300">{item.explanation}</p><p className="mt-2 text-xs text-slate-400">Action: {item.recommended_action}</p>{item.penalty_exposure ? <p className="mt-2 text-xs text-amber-300">{item.penalty_exposure}</p> : null}</article>)}
          </>
        )}
      </div>
    </section>
  )
}
