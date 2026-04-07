import { useMemo, useState } from 'react'
import { fmt, pct, useCreateSimulationScenario, useDeleteSimulationScenario, useRunSimulation, useSimulationScenarios } from '../lib/api'

type Leg = {
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  order_kind: 'MARKET'
}

export default function ScenarioStudio() {
  const { data, isLoading } = useSimulationScenarios()
  const createScenario = useCreateSimulationScenario()
  const deleteScenario = useDeleteSimulationScenario()
  const runSimulation = useRunSimulation()

  const [name, setName] = useState('my_scenario')
  const [description, setDescription] = useState('')
  const [legs, setLegs] = useState<Leg[]>([
    { symbol: 'AAPL', side: 'BUY', quantity: 10, order_kind: 'MARKET' },
    { symbol: 'MSFT', side: 'SELL', quantity: 5, order_kind: 'MARKET' },
  ])

  const scenarios = data?.scenarios ?? []
  const topReasons = useMemo(
    () => runSimulation.data?.summary.top_rejection_reasons ?? [],
    [runSimulation.data],
  )

  return (
    <section className="border-t border-zinc-800/30 pt-6">
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Scenario Studio</h2>

      <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
        <div className="grid gap-2 md:grid-cols-3">
          <input className="glass-input rounded-lg px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="scenario name" />
          <input className="glass-input rounded-lg px-3 py-2 text-sm md:col-span-2" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="description (optional)" />
        </div>

        <div className="mt-3 space-y-2">
          {legs.map((leg, i) => (
            <div key={i} className="grid grid-cols-4 gap-2">
              <input className="glass-input rounded-lg px-2 py-1.5 text-sm" value={leg.symbol} onChange={(e) => {
                const n = [...legs]; n[i] = { ...leg, symbol: e.target.value.toUpperCase() }; setLegs(n)
              }} />
              <select className="glass-input rounded-lg px-2 py-1.5 text-sm" value={leg.side} onChange={(e) => {
                const n = [...legs]; n[i] = { ...leg, side: e.target.value as 'BUY' | 'SELL' }; setLegs(n)
              }}>
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
              <input type="number" className="glass-input rounded-lg px-2 py-1.5 text-sm" value={leg.quantity} min="0.01" step="0.01" onChange={(e) => {
                const n = [...legs]; n[i] = { ...leg, quantity: Number(e.target.value) }; setLegs(n)
              }} />
              <button className="rounded-lg border border-zinc-700/60 px-2 py-1 text-xs text-zinc-400 hover:text-rose-300" onClick={() => setLegs(legs.filter((_, idx) => idx !== i))}>
                Remove
              </button>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button className="rounded-lg border border-zinc-700/60 px-3 py-1.5 text-xs text-zinc-300" onClick={() => setLegs([...legs, { symbol: 'SPY', side: 'BUY', quantity: 1, order_kind: 'MARKET' }])}>+ Add leg</button>
          <button
            className="rounded-lg border border-indigo-500/50 bg-indigo-500/10 px-3 py-1.5 text-xs text-indigo-300"
            onClick={() => createScenario.mutate({ name, description, legs })}
            disabled={createScenario.isPending || !name.trim() || legs.length === 0}
          >
            Save scenario
          </button>
          <button
            className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300"
            onClick={() => runSimulation.mutate({ legs })}
            disabled={runSimulation.isPending || legs.length === 0}
          >
            {runSimulation.isPending ? 'Running…' : 'Run now'}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
          <p className="mb-2 font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">Saved scenarios</p>
          {isLoading ? <p className="text-sm text-zinc-500">Loading…</p> : (
            <div className="space-y-2">
              {scenarios.length === 0 && <p className="text-sm text-zinc-500">No scenarios yet.</p>}
              {scenarios.map((s) => (
                <div key={s.id} className="rounded-lg border border-zinc-800/40 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <p className="font-mono text-xs text-zinc-200">{s.name}</p>
                    <span className="text-[10px] text-zinc-600">{s.legs.length} legs</span>
                    <button className="ml-auto rounded-md border border-zinc-700/60 px-2 py-0.5 text-[10px] text-zinc-400 hover:text-rose-300" onClick={() => deleteScenario.mutate(s.id)}>Delete</button>
                    <button className="rounded-md border border-zinc-700/60 px-2 py-0.5 text-[10px] text-zinc-300 hover:text-emerald-300" onClick={() => runSimulation.mutate({ scenario_id: s.id })}>Run</button>
                  </div>
                  {s.description && <p className="mt-1 text-xs text-zinc-500">{s.description}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
          <p className="mb-2 font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">Last run summary</p>
          {!runSimulation.data ? (
            <p className="text-sm text-zinc-500">Run a scenario to see acceptance and rejection diagnostics.</p>
          ) : (
            <div className="space-y-1 text-sm text-zinc-300">
              <p>Acceptance: <span className="font-mono">{pct(runSimulation.data.summary.acceptance_rate)}</span></p>
              <p>Allowed / Rejected: <span className="font-mono">{runSimulation.data.summary.allowed} / {runSimulation.data.summary.rejected}</span></p>
              <p>Projected allowed notional: <span className="font-mono">{fmt(runSimulation.data.summary.projected_notional_allowed)}</span></p>
              {topReasons.length > 0 && (
                <p>Top blockers: <span className="font-mono">{topReasons.map((r) => `${r.reason}(${r.count})`).join(', ')}</span></p>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
