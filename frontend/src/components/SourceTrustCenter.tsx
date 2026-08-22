import { useEffect, useState } from 'react'
import { fetchSources } from '../services/api'
import type { SourceBrief } from '../types/route'

export default function SourceTrustCenter() {
  const [sources, setSources] = useState<SourceBrief[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchSources().then(setSources).catch(() => setError('Source catalog is unavailable. Apply the latest database migration and retry.'))
  }, [])

  return (
    <section className="space-y-5">
      <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-r from-slate-900 to-cyan-950/30 p-6">
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-300">Nexus SourceLine</p>
        <h2 className="mt-2 text-2xl font-bold">Source Trust Center</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">Provider identity, authority, limits, freshness policy, and attribution. Process health is observational—not a provider SLA.</p>
      </div>
      {error ? <p className="rounded-xl border border-rose-800 bg-rose-950/20 p-4 text-sm text-rose-300">{error}</p> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sources.map((source) => (
          <article key={source.id} className="rounded-xl border border-slate-800 bg-slate-900 p-5">
            <div className="flex items-start justify-between gap-3">
              <div><h3 className="font-semibold text-white">{source.label}</h3><p className="text-xs text-slate-500">{source.category}</p></div>
              <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${source.official ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-800 text-slate-300'}`}>{source.official ? 'OFFICIAL' : 'SUPPLEMENTARY'}</span>
            </div>
            <dl className="mt-4 space-y-2 text-xs">
              <div className="flex justify-between gap-3"><dt className="text-slate-500">Authority</dt><dd className="text-right text-slate-300">{source.authority_level}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500">License</dt><dd className="text-right text-slate-300">{source.license_name ?? 'See provider terms'}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500">API key</dt><dd className="text-right text-slate-300">{source.requires_key ? 'Required' : 'Not required'}</dd></div>
            </dl>
            {source.attribution_text ? <p className="mt-3 text-[11px] text-slate-400">{source.attribution_text}</p> : null}
            {source.reference_url ? <a href={source.reference_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-xs font-semibold text-cyan-400 hover:underline">Provider reference ↗</a> : null}
          </article>
        ))}
      </div>
    </section>
  )
}
