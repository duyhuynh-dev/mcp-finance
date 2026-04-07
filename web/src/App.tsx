import { useState } from 'react'
import {
  fmt,
  fmtPnl,
  useAudit,
  useEquitySeries,
  useFills,
  useOrders,
  usePortfolio,
  useSweepFills,
  useToggleTrading,
  useWebSocket,
} from './lib/api'
import AgentPanel from './components/AgentPanel'
import AlertsPanel from './components/AlertsPanel'
import ApiKeyPanel from './components/ApiKeyPanel'
import AuditTimeline from './components/AuditTimeline'
import BacktestPanel from './components/BacktestPanel'
import ComparisonPanel from './components/ComparisonPanel'
import EquityChart from './components/EquityChart'
import ExecutionQualityPanel from './components/ExecutionQualityPanel'
import FillsTable from './components/FillsTable'
import Header from './components/Header'
import MetricsPanel from './components/MetricsPanel'
import OrderEntryForm from './components/OrderEntryForm'
import OrdersTable from './components/OrdersTable'
import PositionsTable from './components/PositionsTable'
import ReplaySlider from './components/ReplaySlider'
import ReconciliationPanel from './components/ReconciliationPanel'
import RiskPanel from './components/RiskPanel'
import SignalFeed from './components/SignalFeed'
import ScenarioStudio from './components/ScenarioStudio'
import StatCard from './components/StatCard'
import StrategyDashboard from './components/StrategyDashboard'
import StrategyPlayground from './components/StrategyPlayground'
import BrokerStatus from './components/BrokerStatus'
import ApiDisconnected from './components/ApiDisconnected'
import OrderIntentsPanel from './components/OrderIntentsPanel'

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'SPY', 'NVDA', 'AMZN', 'META', 'TSLA', 'QQQ', 'AMD']

const TABS = [
  { id: 'trading', label: 'Trading', icon: '⟐' },
  { id: 'strategy', label: 'Strategy Lab', icon: '◈' },
  { id: 'quant', label: 'Quant Engine', icon: '⬡' },
  { id: 'agents', label: 'Agents', icon: '◉' },
  { id: 'system', label: 'System', icon: '⚙' },
] as const

type TabId = (typeof TABS)[number]['id']

export default function App() {
  useWebSocket()

  const portfolio = usePortfolio()
  const orders = useOrders()
  const fills = useFills()
  const audit = useAudit()
  const equitySeries = useEquitySeries()
  const toggleTrading = useToggleTrading()
  const sweep = useSweepFills()
  const [activeTab, setActiveTab] = useState<TabId>('trading')

  const points = equitySeries.data?.points ?? []
  const p = portfolio.data
  const hasPartials = orders.data?.orders.some((o) => o.status === 'PARTIAL') ?? false

  return (
    <div className="bg-mesh min-h-screen text-zinc-100">
      <Header />

      <main className="mx-auto max-w-[1440px] space-y-5 px-8 py-6">
        {portfolio.isError && (
          <div className="animate-fade-in-up">
            <ApiDisconnected refetch={() => portfolio.refetch()} />
          </div>
        )}

        {/* ── hero stats ──────────────────────────────── */}
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Cash" value={p ? fmt(p.cash) : '—'} sub="available balance" accent="indigo" />
          <StatCard
            label="Equity"
            value={p ? fmt(p.equity) : '—'}
            sub={p ? `Unrealized ${fmtPnl(p.total_unrealized_pnl)}` : '—'}
            accent="emerald"
          />
          <StatCard
            label="Realized P&L"
            value={p ? fmtPnl(p.total_realized_pnl) : '—'}
            sub="cumulative"
            accent={p && p.total_realized_pnl >= 0 ? 'emerald' : 'rose'}
          />
          <div className="glass group relative overflow-hidden rounded-2xl p-5 transition-all duration-300 hover:border-zinc-600/40">
            <div className="absolute left-0 top-0 h-full w-[2px] bg-gradient-to-b from-amber-400 to-amber-400/0" />
            <div className="flex items-center gap-2 mb-2.5">
              <div className="h-1.5 w-1.5 rounded-full bg-amber-400 opacity-60" />
              <p className="font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Trading</p>
            </div>
            <p className="text-lg font-bold font-display">
              {p?.trading_enabled ? (
                <span className="text-emerald-400">Enabled</span>
              ) : (
                <span className="text-rose-400">Kill switch</span>
              )}
            </p>
            <button
              type="button"
              className="glass-input mt-3 w-full rounded-xl py-1.5 text-sm font-medium text-zinc-400 transition-colors hover:text-white hover:border-zinc-600/50"
              onClick={() => toggleTrading.mutate(!p?.trading_enabled)}
              disabled={toggleTrading.isPending || !p}
            >
              {p?.trading_enabled ? 'Disable' : 'Enable'}
            </button>
          </div>
          <div className="glass group relative overflow-hidden rounded-2xl p-5 transition-all duration-300 hover:border-zinc-600/40">
            <div className="absolute left-0 top-0 h-full w-[2px] bg-gradient-to-b from-zinc-500/40 to-zinc-500/0" />
            <div className="flex items-center gap-2 mb-2.5">
              <div className="h-1.5 w-1.5 rounded-full bg-zinc-500 opacity-60" />
              <p className="font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Policy</p>
            </div>
            <div className="space-y-1 font-mono text-[11px] leading-relaxed text-zinc-400">
              <p>max {p?.rules.max_shares_per_symbol ?? '—'} shares/sym</p>
              <p>max {p ? fmt(p.rules.max_order_notional) : '—'}/order</p>
              <p>fee {p?.rules.fee_bps ?? 0} · slip {p?.rules.slippage_bps ?? 0} bps</p>
            </div>
          </div>
        </section>

        {/* ── equity chart ────────────────────────────── */}
        <EquityChart points={points} isLoading={equitySeries.isLoading} />

        {/* ── order entry + replay ────────────────────── */}
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <OrderEntryForm symbols={SYMBOLS} />
          </div>
          <ReplaySlider />
        </div>

        {hasPartials && (
          <div className="glass flex items-center gap-3 rounded-xl px-5 py-3 animate-fade-in-up">
            <div className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
            <span className="text-sm text-amber-200/80">Partial orders awaiting liquidity</span>
            <button
              onClick={() => sweep.mutate()}
              disabled={sweep.isPending}
              className="btn-danger ml-auto rounded-lg px-3 py-1 text-xs font-semibold text-white disabled:opacity-50"
            >
              {sweep.isPending ? 'Sweeping…' : 'Sweep fills'}
            </button>
          </div>
        )}

        {/* ── tabbed sections ─────────────────────────── */}
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
            {activeTab === 'trading' && (
              <div className="space-y-6 animate-fade-in-up">
                <RiskPanel />
                <ReconciliationPanel />
                <div className="grid gap-5 lg:grid-cols-2">
                  <PositionsTable positions={p?.positions} isLoading={portfolio.isLoading} />
                  <OrdersTable orders={orders.data?.orders} isLoading={orders.isLoading} />
                </div>
                <div className="grid gap-5 lg:grid-cols-2">
                  <FillsTable fills={fills.data?.fills} isLoading={fills.isLoading} />
                  <AuditTimeline events={audit.data?.events} isLoading={audit.isLoading} />
                </div>
              </div>
            )}

            {activeTab === 'strategy' && (
              <div className="space-y-6 animate-fade-in-up">
                <BacktestPanel />
                <StrategyPlayground />
                <ScenarioStudio />
                <ComparisonPanel />
              </div>
            )}

            {activeTab === 'quant' && (
              <div className="space-y-6 animate-fade-in-up">
                <StrategyDashboard />
                <SignalFeed />
                <BrokerStatus />
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
                <MetricsPanel />
                <ExecutionQualityPanel />
              </div>
            )}
          </div>
        </div>

        <footer className="pb-8 pt-4 text-center">
          <p className="font-display text-[11px] font-medium tracking-widest text-zinc-600 uppercase">
            Finance Stack · MCP-native paper trading engine
          </p>
        </footer>
      </main>
    </div>
  )
}
