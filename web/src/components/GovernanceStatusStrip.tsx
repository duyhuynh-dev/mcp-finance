import { useAgents, useBrokerStatus, usePendingOrderIntents, useRiskSnapshot } from '../lib/api'

export default function GovernanceStatusStrip() {
  const agents = useAgents()
  const intents = usePendingOrderIntents()
  const risk = useRiskSnapshot()
  const broker = useBrokerStatus()

  const activeAgents = agents.data?.agents.filter((a) => a.is_active).length ?? 0
  const pending = intents.data?.intents.length ?? 0
  const budgetNearLimit = risk.data?.budget?.near_limit ?? false
  const brokerMode = broker.data?.broker.mode ?? broker.data?.backend ?? 'mock'

  return (
    <section className="grid gap-3 md:grid-cols-4">
      <Status label="Agent governance" value={`${activeAgents} active`} tone={activeAgents > 0 ? 'emerald' : 'zinc'} />
      <Status label="Approval queue" value={`${pending} pending`} tone={pending > 0 ? 'amber' : 'emerald'} />
      <Status label="Risk engine" value={budgetNearLimit ? 'Near limit' : 'Guarded'} tone={budgetNearLimit ? 'amber' : 'emerald'} />
      <Status label="Execution mode" value={brokerMode} tone={brokerMode.includes('alpaca') ? 'indigo' : 'zinc'} />
    </section>
  )
}

function Status({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: 'emerald' | 'amber' | 'indigo' | 'zinc'
}) {
  const tones = {
    emerald: 'bg-emerald-400 text-emerald-300',
    amber: 'bg-amber-400 text-amber-300',
    indigo: 'bg-indigo-400 text-indigo-300',
    zinc: 'bg-zinc-500 text-zinc-300',
  }
  return (
    <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 px-4 py-3">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${tones[tone].split(' ')[0]}`} />
        <p className="font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">
          {label}
        </p>
      </div>
      <p className={`mt-1 font-mono text-sm font-semibold ${tones[tone].split(' ')[1]}`}>{value}</p>
    </div>
  )
}
