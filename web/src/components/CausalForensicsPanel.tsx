import { useState } from 'react'
import {
  useCausalChain,
  useCausalCounterfactual,
  useCausalEvents,
  useCausalReplay,
} from '../lib/api'

function displayActor(actor: string) {
  if (!actor) return 'System'
  if (actor === 'human' || actor === 'dashboard') return 'Human'
  if (actor === 'agent') return 'Agent'
  if (actor === 'system') return 'System'
  return actor
}

export default function CausalForensicsPanel() {
  const events = useCausalEvents()
  const replay = useCausalReplay()
  const counter = useCausalCounterfactual()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [maxNotional, setMaxNotional] = useState('1000')
  const chain = useCausalChain(selectedId)
  const selected = chain.data

  const runCounter = () => {
    counter.mutate({
      max_order_notional: Number(maxNotional) || null,
      require_approval_for_all_agents: true,
      limit: 200,
    })
  }

  return (
    <section className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-sm font-bold tracking-tight text-white">
            Audit Forensics
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            One normalized timeline for agent decisions, risk checks, approvals, execution, research, and audit evidence.
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${replay.data?.integrity.ok ? 'bg-emerald-500/10 text-emerald-300' : 'bg-rose-500/10 text-rose-300'}`}>
          audit integrity {replay.data?.integrity.ok ? 'valid' : 'unchecked'}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
        <Stat label="Events" value={String(replay.data?.total_events ?? 0)} />
        <Stat label="Paths" value={String(replay.data?.correlation_count ?? 0)} />
        <Stat label="Allowed" value={String(replay.data?.agent_decisions.ALLOW ?? 0)} />
        <Stat label="Rejected" value={String(replay.data?.agent_decisions.REJECT ?? 0)} />
        <Stat label="Approval" value={String(replay.data?.agent_decisions.REQUIRE_APPROVAL ?? 0)} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
        <div className="space-y-2">
          {(events.data?.events ?? []).map((e) => (
            <button
              key={e.id}
              type="button"
              onClick={() => setSelectedId(e.id)}
              className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                selectedId === e.id
                  ? 'border-indigo-500/50 bg-indigo-500/10'
                  : 'border-zinc-800/30 bg-zinc-950/30 hover:border-zinc-700/60'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-zinc-500">#{e.id}</span>
                <span className="truncate text-xs font-semibold text-zinc-200">{e.event_type}</span>
              </div>
              <p className="mt-1 truncate font-mono text-[11px] text-zinc-600">{e.correlation_id}</p>
            </button>
          ))}
          {!events.data?.events.length && <p className="py-4 text-sm text-zinc-600">No audit events recorded yet.</p>}
        </div>

        <div className="space-y-4">
          {selected ? (
            <>
              <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 p-3">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="rounded bg-indigo-500/10 px-2 py-1 font-mono text-xs text-indigo-300">
                    {selected.correlation_id}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {selected.events.length} linked audit events
                  </span>
                </div>
                <div className="space-y-2">
                  {selected.events.map((e) => (
                    <div key={e.id} className="rounded border border-zinc-800/30 bg-zinc-900/40 px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-mono text-zinc-500">#{e.id}</span>
                        <span className="font-semibold text-zinc-200">{e.event_type}</span>
                        <span className="text-zinc-600">{displayActor(e.actor)}</span>
                        <span className="ml-auto font-mono text-zinc-600">{e.state_hash.slice(0, 12)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 p-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-600">Counterfactual policy</p>
                <div className="flex flex-wrap gap-2">
                  <input
                    className="glass-input w-36 rounded-lg px-2 py-2 font-mono text-sm text-zinc-100"
                    value={maxNotional}
                    onChange={(e) => setMaxNotional(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={runCounter}
                    className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20"
                  >
                    Require approval + cap
                  </button>
                </div>
                {counter.data && (
                  <div className="mt-3 space-y-2">
                    <p className="text-xs text-zinc-400">
                      {counter.data.changed_decisions} of {counter.data.events_evaluated} historical agent decisions would change.
                    </p>
                    {counter.data.changes.slice(0, 5).map((c) => (
                      <div key={c.event_id} className="rounded border border-zinc-800/30 bg-zinc-900/40 px-3 py-2 text-xs">
                        <span className="font-mono text-zinc-500">#{c.event_id}</span>
                        <span className="ml-2 text-zinc-300">{c.original_decision}</span>
                        <span className="mx-2 text-zinc-600">to</span>
                        <span className="text-amber-300">{c.counterfactual_decision}</span>
                        <span className="ml-2 text-zinc-600">{c.reasons.join(', ')}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 p-8 text-center text-sm text-zinc-600">
              Select an audit event to inspect its decision path.
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-zinc-200">{value}</p>
    </div>
  )
}
