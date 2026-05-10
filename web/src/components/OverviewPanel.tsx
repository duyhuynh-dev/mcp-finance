import {
  fmt,
  fmtPnl,
  useAgents,
  useBrokerStatus,
  useCausalReplay,
  usePendingOrderIntents,
  usePortfolio,
  useResearchRuns,
  useRiskSnapshot,
  useVenueStatus,
} from '../lib/api'
import EquityChart from './EquityChart'
import GovernanceStatusStrip from './GovernanceStatusStrip'
import StatCard from './StatCard'

export default function OverviewPanel({ equityPoints }: { equityPoints: Array<{ ts: string; equity: number }> }) {
  const portfolio = usePortfolio()
  const agents = useAgents()
  const intents = usePendingOrderIntents()
  const risk = useRiskSnapshot()
  const research = useResearchRuns(5)
  const venue = useVenueStatus()
  const replay = useCausalReplay()
  const broker = useBrokerStatus()

  const p = portfolio.data
  const activeAgents = agents.data?.agents.filter((a) => a.is_active).length ?? 0
  const latestResearch = research.data?.runs[0]
  const pending = intents.data?.intents.length ?? 0
  const riskMode = risk.data?.budget?.near_limit ? 'Near limit' : 'Guarded'
  const venueOpen = (venue.data?.orders_by_status.OPEN ?? 0) + (venue.data?.orders_by_status.PARTIAL ?? 0)
  const flowSteps = [
    {
      label: 'Agent',
      value: activeAgents > 0 ? `${activeAgents} active` : 'Register agent',
      tone: activeAgents > 0 ? 'emerald' : 'zinc',
    },
    {
      label: 'Proposal',
      value: pending > 0 ? `${pending} awaiting review` : 'No pending trades',
      tone: pending > 0 ? 'amber' : 'zinc',
    },
    {
      label: 'Risk decision',
      value: riskMode,
      tone: risk.data?.budget?.near_limit ? 'amber' : 'emerald',
    },
    {
      label: 'Execution',
      value: `${venueOpen} venue orders`,
      tone: venueOpen > 0 ? 'indigo' : 'zinc',
    },
    {
      label: 'Evidence',
      value: `${replay.data?.total_events ?? 0} events`,
      tone: replay.data?.integrity.ok ? 'emerald' : 'zinc',
    },
  ] as const

  return (
    <div className="space-y-5 animate-fade-in-up">
      <section className="rounded-2xl border border-zinc-800/40 bg-zinc-950/40 px-5 py-5">
        <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
          <div className="min-w-0">
            <p className="font-display text-[10px] font-bold uppercase tracking-[0.18em] text-indigo-300">
              Governed Financial Agency
            </p>
            <h2 className="mt-2 max-w-4xl font-display text-2xl font-bold leading-tight tracking-tight text-white">
              Validate strategies, constrain agents, approve risk, execute realistically, and replay the evidence.
            </h2>
            <div className="mt-5 grid gap-2 md:grid-cols-5">
              {flowSteps.map((step, index) => (
                <FlowStep
                  key={step.label}
                  index={index + 1}
                  label={step.label}
                  value={step.value}
                  tone={step.tone}
                />
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-zinc-800/40 bg-zinc-900/40 px-4 py-4">
            <p className="text-[10px] uppercase tracking-widest text-emerald-300">Integrity</p>
            <p className="mt-1 font-mono text-base font-semibold text-white">
              {replay.data?.integrity.ok ? 'Audit integrity valid' : 'Waiting for events'}
            </p>
            <p className="mt-3 text-xs leading-5 text-zinc-500">
              Every proposed, approved, rejected, simulated, or filled action is recorded as replayable evidence.
            </p>
          </div>
        </div>
      </section>

      <GovernanceStatusStrip />

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Equity" value={p ? fmt(p.equity) : '-'} sub={p ? `Unrealized ${fmtPnl(p.total_unrealized_pnl)}` : '-'} accent="emerald" />
        <StatCard label="Active agents" value={String(activeAgents)} sub={`${pending} approvals pending`} accent={pending ? 'rose' : 'indigo'} />
        <StatCard label="Risk posture" value={riskMode} sub={`Gross ${risk.data?.gross_exposure_multiple ?? 0}x`} accent={risk.data?.budget?.near_limit ? 'rose' : 'emerald'} />
        <StatCard label="Venue" value={`${venueOpen} open`} sub={`${venue.data?.fills.count ?? 0} fills mirrored`} accent="indigo" />
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <EquityChart points={equityPoints} isLoading={portfolio.isLoading} />
        <section className="rounded-2xl border border-zinc-800/30 bg-zinc-900/30 p-4">
          <h3 className="font-display text-sm font-bold text-white">Evidence Brief</h3>
          <div className="mt-4 space-y-3 text-sm">
            <Brief label="Latest research" value={latestResearch ? `${latestResearch.strategy_name} · Sharpe ${latestResearch.metrics.sharpe.toFixed(2)}` : 'No report yet'} />
            <Brief label="Broker mode" value={broker.data?.broker.mode ?? broker.data?.backend ?? 'mock'} />
            <Brief label="Audit events" value={`${replay.data?.total_events ?? 0} recorded`} />
            <Brief label="Venue quality" value={`${(venue.data?.fills.avg_spread_bps ?? 0).toFixed(2)} bps spread · ${(venue.data?.fills.avg_impact_bps ?? 0).toFixed(2)} bps impact`} />
          </div>
        </section>
      </div>
    </div>
  )
}

function FlowStep({
  index,
  label,
  value,
  tone,
}: {
  index: number
  label: string
  value: string
  tone: 'emerald' | 'amber' | 'indigo' | 'zinc'
}) {
  const tones = {
    emerald: 'border-emerald-500/25 bg-emerald-500/5 text-emerald-300',
    amber: 'border-amber-500/25 bg-amber-500/5 text-amber-300',
    indigo: 'border-indigo-500/25 bg-indigo-500/5 text-indigo-300',
    zinc: 'border-zinc-800/40 bg-zinc-950/30 text-zinc-400',
  }
  return (
    <div className={`rounded-xl border px-3 py-3 ${tones[tone]}`}>
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-950/70 font-mono text-[10px] text-zinc-400">
          {index}
        </span>
        <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</p>
      </div>
      <p className="mt-2 truncate font-mono text-xs font-semibold">{value}</p>
    </div>
  )
}

function Brief({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800/30 bg-zinc-950/30 px-3 py-3">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-1 font-mono text-xs text-zinc-200">{value}</p>
    </div>
  )
}
