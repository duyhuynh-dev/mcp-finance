import { useState } from 'react'
import { fmt, useAgents, useAgentStats, useRegisterAgent } from '../lib/api'
import ApiDisconnected from './ApiDisconnected'
import LoadingSkeleton from './LoadingSkeleton'

export default function AgentPanel() {
  const { data, isPending, isError, refetch } = useAgents()
  const register = useRegisterAgent()
  const [newName, setNewName] = useState('')
  const [newBudget, setNewBudget] = useState('50000')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const { data: stats } = useAgentStats(selectedId)

  const handleRegister = () => {
    if (!newName.trim()) return
    register.mutate(
      { name: newName.trim(), budget: Number(newBudget) },
      { onSuccess: () => { setNewName(''); setNewBudget('50000') } },
    )
  }

  return (
    <section>
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Agent Orchestration</h2>

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Name</label>
          <input
            className="glass-input w-36 rounded-lg px-3 py-2 font-mono text-sm text-zinc-100"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="alpha-1"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Budget</label>
          <input
            type="number"
            className="glass-input w-28 rounded-lg px-3 py-2 font-mono text-sm text-zinc-100"
            value={newBudget}
            onChange={(e) => setNewBudget(e.target.value)}
          />
        </div>
        <button
          type="button"
          className="rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/10 transition-all hover:shadow-indigo-500/20 hover:brightness-110 disabled:opacity-50"
          onClick={handleRegister}
          disabled={register.isPending}
        >
          Register Agent
        </button>
      </div>

      {isError ? (
        <ApiDisconnected refetch={() => refetch()} compact />
      ) : isPending ? (
        <LoadingSkeleton rows={2} />
      ) : !data?.agents.length ? (
        <p className="text-sm text-zinc-600">No agents registered.</p>
      ) : (
        <div className="space-y-2">
          {data.agents.map((a) => (
            <button
              key={a.id}
              type="button"
              className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition-all duration-200 ${
                selectedId === a.id
                  ? 'border-indigo-500/40 bg-indigo-950/20'
                  : 'border-zinc-800/30 bg-zinc-900/30 hover:border-zinc-700/50'
              }`}
              onClick={() => setSelectedId(selectedId === a.id ? null : a.id)}
            >
              <span className="font-mono font-medium text-indigo-300">{a.name}</span>
              <span className="ml-3 text-zinc-600">budget {fmt(a.budget)}</span>
              {!a.is_active && <span className="ml-2 text-[11px] text-rose-400">inactive</span>}
            </button>
          ))}
        </div>
      )}

      {stats && (
        <div className="mt-4 rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
          <p className="mb-3 text-xs font-semibold text-indigo-300">{stats.agent_name} — Performance</p>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <Kv label="Orders" value={String(stats.total_orders)} />
            <Kv label="Filled" value={String(stats.filled_orders)} />
            <Kv label="Rejected" value={String(stats.rejected_orders)} />
            <Kv label="Notional" value={fmt(stats.total_notional)} />
            <Kv label="Fees" value={fmt(stats.total_fees)} />
            <Kv label="Realized P&L" value={fmt(stats.realized_pnl)} color={stats.realized_pnl >= 0} />
            <Kv label="Budget Used" value={fmt(stats.budget_used)} />
            <Kv label="Remaining" value={fmt(stats.budget_remaining)} />
          </div>
          {Object.keys(stats.positions).length > 0 && (
            <div className="mt-3">
              <p className="text-[11px] text-zinc-600">Positions</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {Object.entries(stats.positions).map(([sym, qty]) => (
                  <span key={sym} className="rounded-md bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] text-emerald-300">
                    {sym}: {qty}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function Kv({ label, value, color }: { label: string; value: string; color?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800/20 bg-zinc-900/40 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className={`mt-0.5 font-mono text-sm ${color === true ? 'text-emerald-400' : color === false ? 'text-rose-400' : 'text-zinc-200'}`}>
        {value}
      </p>
    </div>
  )
}
