import { useEffect, useState } from 'react'
import { LOCAL_DEMO_MODE, supabase } from '../services/supabaseClient'

export type ActiveTab =
  | 'command' | 'predictive' | 'dustRadar' | 'analytics' | 'history'
  | 'dispatch' | 'schedule' | 'weather' | 'loadProfiles' | 'liveTraffic'
  | 'sourceTrust' | 'compliance'
  | 'liveOps'
  | 'integrated'

interface HeaderNavbarProps {
  activeTab: ActiveTab
  setActiveTab: (tab: ActiveTab) => void
}

const tabs: Array<[ActiveTab, string]> = [
  ['integrated', '🧭 Nexus v6'], ['liveOps', '🟢 LiveOps'], ['command', '📍 Operations'], ['schedule', '🗓 Scheduler'], ['dispatch', '🚦 Dispatch'],
  ['predictive', '⚡ Predictive ETA'], ['dustRadar', '🌪️ Dust Radar'], ['analytics', '📊 Analytics'],
  ['history', '📜 Audit'], ['weather', '🌦️ Telemetry'], ['liveTraffic', '🛰️ Live Traffic'],
  ['loadProfiles', '📦 Loads'],
  ['sourceTrust', '🔎 Sources'], ['compliance', '🛡️ Compliance'],
]

export default function HeaderNavbar({ activeTab, setActiveTab }: HeaderNavbarProps) {
  const [email, setEmail] = useState<string>('Operator')

  useEffect(() => {
    if (LOCAL_DEMO_MODE) {
      setEmail('Local demo operator')
      return
    }
    void supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? 'Operator'))
  }, [])

  return (
    <header className="bg-slate-950/90 border-b border-slate-800/80 backdrop-blur-md sticky top-0 z-40 px-4 py-3">
      <div className="max-w-7xl mx-auto flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-xl">🚆</div>
            <div>
              <h1 className="text-lg font-bold">ClearPath Nexus <span className="text-[10px] text-amber-400">v6.0</span></h1>
              <p className="text-[11px] text-slate-400">Explainable Freight Operations Decision Support</p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5">
            <span className="max-w-48 truncate text-xs text-slate-300">👤 {email}</span>
            {!LOCAL_DEMO_MODE && <button onClick={() => void supabase.auth.signOut()} className="text-[11px] text-rose-400 hover:underline">Sign Out</button>}
          </div>
        </div>
        <nav className="flex flex-wrap items-center gap-1 bg-slate-900/90 p-1 border border-slate-800 rounded-xl">
          {tabs.map(([id, label]) => (
            <button key={id} onClick={() => setActiveTab(id)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeTab === id ? 'bg-cyan-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}>
              {label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  )
}
