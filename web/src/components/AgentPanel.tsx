import { useState } from 'react'
import { fmt, useAgents, useAgentStats, useRecentAgentActions, useRegisterAgent } from '../lib/api'
import type { AgentData } from '../lib/types'
import ApiDisconnected from './ApiDisconnected'
import LoadingSkeleton from './LoadingSkeleton'

export default function AgentPanel() {
  const { data, isPending, isError, refetch } = useAgents()
  const register = useRegisterAgent()
  const [newName, setNewName] = useState('')
  const [newBudget, setNewBudget] = useState('50000')
  const [newSymbols, setNewSymbols] = useState('AAPL,MSFT,SPY')
  const [newTools, setNewTools] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const { data: stats } = useAgentStats(selectedId)
  const { data: actions } = useRecentAgentActions()

  const handleRegister = () => {
    if (!newName.trim()) return
    const allowed_mcp_tools = newTools
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    register.mutate(
      {
        name: newName.trim(),
        budget: Number(newBudget),
        allowed_symbols: newSymbols.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean),
        allowed_mcp_tools: allowed_mcp_tools.length ? allowed_mcp_tools : null,
      },
      { onSuccess: () => { setNewName(''); setNewBudget('50000'); setNewSymbols('AAPL,MSFT,SPY'); setNewTools('') } },
    )
  }

  return (
    <section>
      <div className="mb-4">
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Governed Agent Orchestration</h2>
        <p className="mt-1 text-xs text-zinc-500">Agents are constrained by budgets, symbol scopes, MCP tool scopes, and reviewable actions.</p>
      </div>

      <div className="mb-5 rounded-xl border border-zinc-800/30 bg-zinc-950/30 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-zinc-200">Register constrained agent</p>
            <p className="mt-1 text-xs text-zinc-600">This creates an identity with hard trading limits, not an autonomous money machine.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
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
        <div className="min-w-[18rem]">
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">
            Allowed symbols
          </label>
          <input
            className="glass-input w-full rounded-lg px-3 py-2 font-mono text-sm text-zinc-100"
            value={newSymbols}
            onChange={(e) => setNewSymbols(e.target.value)}
            placeholder="AAPL,MSFT,SPY"
          />
        </div>
        <div className="min-w-[18rem]">
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">
            MCP tools (comma-separated)
          </label>
          <input
            className="glass-input w-full rounded-lg px-3 py-2 font-mono text-sm text-zinc-100"
            value={newTools}
            onChange={(e) => setNewTools(e.target.value)}
            placeholder="place_order,run_quant_strategies_once"
          />
        </div>
        </div>
      </div>

      {isError ? (
        <ApiDisconnected refetch={() => refetch()} compact />
      ) : isPending ? (
        <LoadingSkeleton rows={2} />
      ) : !data?.agents.length ? (
        <p className="text-sm text-zinc-600">No agents registered.</p>
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {data.agents.map((a) => (
            <button
              key={a.id}
              type="button"
              className={`w-full rounded-xl border px-4 py-4 text-left text-sm transition-all duration-200 ${
                selectedId === a.id
                  ? 'border-indigo-500/40 bg-indigo-950/20'
                  : 'border-zinc-800/30 bg-zinc-900/30 hover:border-zinc-700/50'
              }`}
              onClick={() => setSelectedId(selectedId === a.id ? null : a.id)}
            >
              <AgentCardBody agent={a} selected={selectedId === a.id} />
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

      <div className="mt-4 rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
        <p className="mb-3 text-xs font-semibold text-indigo-300">Recent Governed Actions</p>
        {!actions?.actions.length ? (
          <p className="text-sm text-zinc-600">No agent actions recorded yet.</p>
        ) : (
          <div className="space-y-2">
            {actions.actions.slice(0, 6).map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2 text-xs">
                <span className="font-mono text-zinc-500">#{a.id}</span>
                <span className="text-indigo-300">{a.agent_name ?? `agent ${a.agent_id ?? '-'}`}</span>
                <span className="text-zinc-400">{a.action}</span>
                <span className={`rounded px-2 py-0.5 font-semibold ${a.decision === 'REJECT' ? 'bg-rose-500/10 text-rose-300' : a.decision === 'REQUIRE_APPROVAL' ? 'bg-amber-500/10 text-amber-300' : 'bg-emerald-500/10 text-emerald-300'}`}>
                  {a.decision}
                </span>
                <span className="ml-auto font-mono text-zinc-600">{new Date(a.ts).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function AgentCardBody({ agent, selected }: { agent: AgentData; selected: boolean }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${agent.is_active ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            <p className="truncate font-mono text-sm font-semibold text-indigo-300">{agent.name}</p>
          </div>
          <p className="mt-1 text-xs text-zinc-600">
            {agent.is_active ? 'Active governed agent' : 'Inactive agent'} · click to inspect performance
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest ${
          selected ? 'bg-indigo-500/15 text-indigo-300' : 'bg-zinc-800/60 text-zinc-400'
        }`}>
          {selected ? 'Selected' : 'Constrained'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Mini label="Budget" value={fmt(agent.budget)} />
        <Mini label="Max order" value={fmt(agent.max_order_notional)} />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <TokenGroup label="Allowed symbols" values={agent.allowed_symbols} empty="No symbols allowed" tone="emerald" />
        <TokenGroup label="Allowed MCP tools" values={agent.allowed_mcp_tools ?? []} empty="Dashboard only" tone="indigo" />
      </div>
    </div>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-0.5 font-mono text-sm text-zinc-100">{value}</p>
    </div>
  )
}

function TokenGroup({
  label,
  values,
  empty,
  tone,
}: {
  label: string
  values: string[]
  empty: string
  tone: 'emerald' | 'indigo'
}) {
  const cls = tone === 'emerald' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-indigo-500/10 text-indigo-300'
  return (
    <div>
      <p className="mb-1.5 text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      {values.length ? (
        <div className="flex flex-wrap gap-1.5">
          {values.slice(0, 6).map((value) => (
            <span key={value} className={`rounded px-2 py-0.5 font-mono text-[10px] ${cls}`}>
              {value}
            </span>
          ))}
          {values.length > 6 && <span className="text-[10px] text-zinc-600">+{values.length - 6}</span>}
        </div>
      ) : (
        <p className="font-mono text-[11px] text-zinc-600">{empty}</p>
      )}
    </div>
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
