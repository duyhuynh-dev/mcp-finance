import {
  useApproveOrderIntent,
  usePendingOrderIntents,
  useRejectOrderIntent,
} from '../lib/api'
import LoadingSkeleton from './LoadingSkeleton'

export default function OrderIntentsPanel() {
  const { data, isPending } = usePendingOrderIntents()
  const approve = useApproveOrderIntent()
  const reject = useRejectOrderIntent()
  const intents = data?.intents ?? []

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-sm font-bold tracking-tight text-white">
            Human Approval Queue
          </h2>
          <p className="mt-1 text-xs text-zinc-500">Agent proposals wait here until a human accepts the final risk check.</p>
        </div>
        <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-300">
          {intents.length} pending
        </span>
      </div>
      {isPending ? (
        <LoadingSkeleton rows={2} />
      ) : intents.length === 0 ? (
        <div className="rounded-xl border border-zinc-800/30 bg-zinc-950/30 px-4 py-6 text-center">
          <p className="text-sm font-medium text-zinc-400">No pending approvals</p>
          <p className="mt-1 text-xs text-zinc-600">Agent proposals that require human review will appear here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {intents.map((x) => (
            <div
              key={x.id}
              className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 px-4 py-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm text-indigo-300">{x.client_order_id}</span>
                    {x.agent_id != null && (
                      <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[11px] text-indigo-300">
                        agent #{x.agent_id}
                      </span>
                    )}
                    <span className="rounded bg-zinc-800/70 px-2 py-0.5 text-[11px] text-zinc-300">
                      {x.order_kind}
                    </span>
                  </div>
                  <p className="mt-2 font-display text-xl font-bold tracking-tight text-white">
                    {x.side} {x.quantity} {x.symbol}
                  </p>
                </div>
                <div className="text-right">
                  <DecisionBadge decision={x.decision?.decision ?? 'PENDING'} />
                  <p className="mt-2 font-mono text-[11px] text-zinc-600">
                    {new Date(x.created_at).toLocaleTimeString()}
                  </p>
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-600">Why review is needed</p>
                <p className="mt-1 font-mono text-xs text-zinc-300">{x.reason ?? x.decision?.reason ?? 'manual review'}</p>
              </div>
              {x.decision?.checks && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {x.decision.checks.slice(0, 6).map((c) => (
                    <span
                      key={c.name}
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                        c.passed ? 'bg-emerald-500/10 text-emerald-300' : 'bg-rose-500/10 text-rose-300'
                      }`}
                    >
                      {c.name.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  className="rounded-lg bg-emerald-600/90 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                  onClick={() => approve.mutate(x.id)}
                  disabled={approve.isPending}
                >
                  {approve.isPending ? 'Approving...' : 'Approve'}
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-rose-500/35 bg-rose-500/10 px-4 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-500/20 disabled:opacity-50"
                  onClick={() => reject.mutate(x.id)}
                  disabled={reject.isPending}
                >
                  {reject.isPending ? 'Rejecting...' : 'Reject'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function DecisionBadge({ decision }: { decision: string }) {
  const cls =
    decision === 'REJECT'
      ? 'bg-rose-500/10 text-rose-300'
      : decision === 'REQUIRE_APPROVAL' || decision === 'PENDING'
        ? 'bg-amber-500/10 text-amber-300'
        : decision === 'RESIZE'
          ? 'bg-indigo-500/10 text-indigo-300'
          : 'bg-emerald-500/10 text-emerald-300'
  return (
    <span className={`rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-widest ${cls}`}>
      {decision}
    </span>
  )
}
