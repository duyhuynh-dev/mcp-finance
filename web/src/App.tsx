import { useEffect, useState } from 'react'
import {
  useAudit,
  useEquitySeries,
  useFills,
  useOrders,
  usePortfolio,
  useWebSocket,
} from './lib/api'
import AgentPanel from './components/AgentPanel'
import AlertsPanel from './components/AlertsPanel'
import ApiKeyPanel from './components/ApiKeyPanel'
import AuditTimeline from './components/AuditTimeline'
import BacktestPanel from './components/BacktestPanel'
import ComparisonPanel from './components/ComparisonPanel'
import CausalForensicsPanel from './components/CausalForensicsPanel'
import ExecutionQualityPanel from './components/ExecutionQualityPanel'
import FillsTable from './components/FillsTable'
import Header from './components/Header'
import MetricsPanel from './components/MetricsPanel'
import OrderEntryForm from './components/OrderEntryForm'
import OrdersTable from './components/OrdersTable'
import OverviewPanel from './components/OverviewPanel'
import PositionsTable from './components/PositionsTable'
import ReplaySlider from './components/ReplaySlider'
import ReconciliationPanel from './components/ReconciliationPanel'
import ResearchReportsPanel from './components/ResearchReportsPanel'
import RiskPanel from './components/RiskPanel'
import SignalFeed from './components/SignalFeed'
import ScenarioStudio from './components/ScenarioStudio'
import StrategyDashboard from './components/StrategyDashboard'
import StrategyPlayground from './components/StrategyPlayground'
import BrokerStatus from './components/BrokerStatus'
import ApiDisconnected from './components/ApiDisconnected'
import OrderIntentsPanel from './components/OrderIntentsPanel'
import TradeDecisionPanel from './components/TradeDecisionPanel'
import VenuePanel from './components/VenuePanel'
import LandingPage from './components/LandingPage'
import MethodologyPage from './components/MethodologyPage'

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'SPY', 'NVDA', 'AMZN', 'META', 'TSLA', 'QQQ', 'AMD']

const TABS = [
  { id: 'overview', label: 'Overview', icon: '⌁' },
  { id: 'agents', label: 'Agents', icon: '◉' },
  { id: 'research', label: 'Research', icon: '◈' },
  { id: 'execution', label: 'Execution', icon: '⟐' },
  { id: 'forensics', label: 'Forensics', icon: '◇' },
  { id: 'system', label: 'System', icon: '⚙' },
] as const

type TabId = (typeof TABS)[number]['id']

export default function App() {
  const [path, setPath] = useState(() => window.location.pathname)

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = (nextPath: string) => {
    window.history.pushState({}, '', nextPath)
    setPath(nextPath)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (path === '/methodology') {
    return <MethodologyPage onBack={() => navigate('/')} onEnterApp={() => navigate('/app')} />
  }

  if (path !== '/app') {
    return <LandingPage onEnterApp={() => navigate('/app')} onOpenDocs={() => navigate('/methodology')} />
  }

  return <ControlPlane />
}

function ControlPlane() {
  useWebSocket()

  const portfolio = usePortfolio()
  const orders = useOrders()
  const fills = useFills()
  const audit = useAudit()
  const equitySeries = useEquitySeries()
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  const points = equitySeries.data?.points ?? []
  const p = portfolio.data

  return (
    <div className="bg-mesh min-h-screen text-zinc-100">
      <Header />

      <main className="mx-auto max-w-[1440px] space-y-5 px-8 py-6">
        {portfolio.isError && (
          <div className="animate-fade-in-up">
            <ApiDisconnected refetch={() => portfolio.refetch()} />
          </div>
        )}

        <div className="glass rounded-2xl overflow-hidden">
          <nav className="flex border-b border-zinc-800/40 px-2 pt-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex items-center gap-2 px-5 py-3 text-[13px] font-semibold transition-all duration-200 rounded-t-lg ${
                  activeTab === tab.id
                    ? 'text-white bg-zinc-800/30'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <span className="text-[14px] opacity-60">{tab.icon}</span>
                {tab.label}
                {activeTab === tab.id && (
                  <span className="absolute bottom-0 left-2 right-2 h-[2px] rounded-full bg-gradient-to-r from-indigo-400 to-emerald-400" />
                )}
              </button>
            ))}
          </nav>

          <div className="p-6 bg-noise">
            {activeTab === 'overview' && (
              <OverviewPanel equityPoints={points} />
            )}

            {activeTab === 'execution' && (
              <div className="space-y-6 animate-fade-in-up">
                <div className="grid gap-5 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <OrderEntryForm symbols={SYMBOLS} />
                  </div>
                  <ReplaySlider />
                </div>
                <div className="grid gap-5 xl:grid-cols-2">
                  <TradeDecisionPanel />
                  <VenuePanel />
                </div>
                <div className="grid gap-5 lg:grid-cols-2">
                  <PositionsTable positions={p?.positions} isLoading={portfolio.isLoading} />
                  <OrdersTable orders={orders.data?.orders} isLoading={orders.isLoading} />
                </div>
                <div className="grid gap-5 lg:grid-cols-2">
                  <FillsTable fills={fills.data?.fills} isLoading={fills.isLoading} />
                  <AuditTimeline events={audit.data?.events} isLoading={audit.isLoading} />
                </div>
                <ReconciliationPanel />
              </div>
            )}

            {activeTab === 'research' && (
              <div className="space-y-6 animate-fade-in-up">
                <ResearchReportsPanel />
                <BacktestPanel />
                <StrategyPlayground />
                <ScenarioStudio />
                <ComparisonPanel />
              </div>
            )}

            {activeTab === 'forensics' && (
              <div className="space-y-6 animate-fade-in-up">
                <CausalForensicsPanel />
                <div className="grid gap-5 lg:grid-cols-2">
                  <AuditTimeline events={audit.data?.events} isLoading={audit.isLoading} />
                  <ReplaySlider />
                </div>
              </div>
            )}

            {activeTab === 'agents' && (
              <div className="space-y-6 animate-fade-in-up">
                <AgentPanel />
                <OrderIntentsPanel />
                <AlertsPanel />
              </div>
            )}

            {activeTab === 'system' && (
              <div className="space-y-6 animate-fade-in-up">
                <ApiKeyPanel />
                <RiskPanel />
                <StrategyDashboard />
                <SignalFeed />
                <BrokerStatus />
                <MetricsPanel />
                <ExecutionQualityPanel />
              </div>
            )}
          </div>
        </div>

        <footer className="pb-8 pt-4 text-center">
          <p className="font-display text-[11px] font-medium tracking-widest text-zinc-600 uppercase">
            Agent Control Plane · MCP-native trading control plane
          </p>
        </footer>
      </main>
    </div>
  )
}
