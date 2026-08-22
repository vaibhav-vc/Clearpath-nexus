import { lazy, Suspense, useState } from 'react'
import AuthGate from './components/AuthGate'
import HeaderNavbar, { type ActiveTab } from './components/HeaderNavbar'
import { LOCAL_DEMO_MODE } from './services/supabaseClient'

const CommandDashboard = lazy(() => import('./components/DashboardTab'))
const RouteHistoryPanel = lazy(() => import('./components/RouteHistoryPanel'))
const RouteHistory = lazy(() => import('./components/RouteHistory'))
const ScheduleBoard = lazy(() => import('./components/ScheduleBoard'))
const WeatherIntelligenceView = lazy(() => import('./components/WeatherIntelligenceView'))
const PredictiveDelayPanel = lazy(() => import('./components/PredictiveDelayPanel'))
const DustStormRadarPanel = lazy(() => import('./components/DustStormRadarPanel'))
const LiveCorridorTrafficPanel = lazy(() => import('./components/LiveCorridorTrafficPanel'))
const AnalyticsDashboardView = lazy(() => import('./components/AnalyticsDashboardView'))
const LoadProfilePanel = lazy(() => import('./components/LoadProfilePanel'))
const SourceTrustCenter = lazy(() => import('./components/SourceTrustCenter'))
const ComplianceGuard = lazy(() => import('./components/ComplianceGuard'))
const LiveOps = lazy(() => import('./components/LiveOps'))
const IntegratedOperations = lazy(() => import('./components/IntegratedOperations'))

function OperationsApp() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('command')
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col">
      <HeaderNavbar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        <Suspense fallback={<div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 text-sm text-slate-400">Loading operations module…</div>}>
        {activeTab === 'command' && <CommandDashboard />}
        {activeTab === 'predictive' && <PredictiveDelayPanel />}
        {activeTab === 'dustRadar' && <DustStormRadarPanel />}
        {activeTab === 'analytics' && <AnalyticsDashboardView />}
        {activeTab === 'history' && <RouteHistoryPanel />}
        {activeTab === 'dispatch' && <RouteHistory onBack={() => setActiveTab('command')} onSchedule={() => setActiveTab('schedule')} />}
        {activeTab === 'schedule' && <ScheduleBoard onBack={() => setActiveTab('command')} onHistory={() => setActiveTab('dispatch')} />}
        {activeTab === 'weather' && <WeatherIntelligenceView />}
        {activeTab === 'liveTraffic' && <LiveCorridorTrafficPanel />}
        {activeTab === 'sourceTrust' && <SourceTrustCenter />}
        {activeTab === 'compliance' && <ComplianceGuard />}
        {activeTab === 'liveOps' && <LiveOps />}
        {activeTab === 'integrated' && <IntegratedOperations />}
        {activeTab === 'loadProfiles' && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <h2 className="text-xl font-bold text-slate-100">📦 Cargo Load Profiles</h2>
            <p className="mb-4 mt-1 text-xs text-slate-400">Manage cargo constraints for rapid route evaluations.</p>
            <LoadProfilePanel
              selectedId={selectedProfileId}
              onSelect={(profile) => setSelectedProfileId(profile?.id ?? null)}
              onContinue={() => setActiveTab('command')}
            />
          </div>
        )}
        </Suspense>
      </main>
      <footer className="bg-slate-950 border-t border-slate-900 py-4 px-6 text-center text-xs text-slate-500">
        ClearPath Nexus v6.0 • {LOCAL_DEMO_MODE ? 'Local development demo — authentication disabled' : 'Supabase-secured integrated freight decision support'}
      </footer>
    </div>
  )
}

export default function App() {
  return <AuthGate><OperationsApp /></AuthGate>
}
