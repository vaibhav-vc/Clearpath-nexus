export default function AnalyticsDashboardView() {
  return (
    <div className="space-y-6 text-slate-100">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <span>📊</span> Executive Operational Analytics & Performance Metrics
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Corridor throughput, average dwell times, RRI distribution, & delay risk mitigation KPIs
            </p>
          </div>
          <div className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs font-semibold text-emerald-400">
            ● Live Network Health: 96.2% Operational
          </div>
        </div>

        {/* High Level KPI Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 font-semibold uppercase">Total Dispatches Evaluated</div>
            <div className="text-3xl font-extrabold text-cyan-400 mt-1">1,428</div>
            <div className="text-[11px] text-emerald-400 mt-1">↑ +14.2% vs last month</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 font-semibold uppercase">Network Average RRI</div>
            <div className="text-3xl font-extrabold text-emerald-400 mt-1">87.4</div>
            <div className="text-[11px] text-slate-400 mt-1">Target threshold ≥ 80.0</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 font-semibold uppercase">Port Sync Accuracy</div>
            <div className="text-3xl font-extrabold text-cyan-400 mt-1">94.8%</div>
            <div className="text-[11px] text-emerald-400 mt-1">JNPT berth window alignment</div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
            <div className="text-xs text-slate-400 font-semibold uppercase">Clearance Block Prevention</div>
            <div className="text-3xl font-extrabold text-rose-400 mt-1">42</div>
            <div className="text-[11px] text-slate-400 mt-1">Over-dimensional collisions averted</div>
          </div>
        </div>

        {/* Analytics Breakdown Visuals */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-bold text-slate-200 mb-4">Corridor Risk Distribution</h3>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Nagpur → Bhusaval (NGP → BSL)</span>
                  <span className="text-emerald-400 font-bold">RRI 92</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: '92%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Bhusaval → Manmad (BSL → MMR)</span>
                  <span className="text-emerald-400 font-bold">RRI 88</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: '88%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Manmad → Kalyan (MMR → KYN)</span>
                  <span className="text-amber-400 font-bold">RRI 74</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: '74%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Kalyan → JNPT Port (KYN → JNPT)</span>
                  <span className="text-amber-400 font-bold">RRI 68</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: '68%' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-200 mb-2">Delay Mitigation Impact</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Live operational impact metrics appear here after route-history data is collected. The current benchmark card is illustrative only and is not a measured production KPI.
              </p>
            </div>
            <div className="mt-4 p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-xs text-cyan-300">
              💡 Port synchronization requires a configured maritime provider; no provider-backed reduction is claimed by default.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
