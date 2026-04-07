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
      <h2 className="mb-3 font-display text-sm font-bold tracking-tight text-white">
        Pending Order Intents
      </h2>
      {isPending ? (
        <LoadingSkeleton rows={2} />
      ) : intents.length === 0 ? (
        <p className="py-4 text-sm text-zinc-600">No pending intents.</p>
      ) : (
        <div className="space-y-2">
          {intents.map((x) => (
            <div
              key={x.id}
              className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 px-4 py-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm text-indigo-300">{x.client_order_id}</span>
                <span className="rounded bg-zinc-800/70 px-2 py-0.5 text-[11px] text-zinc-300">
                  {x.symbol} {x.side} {x.quantity}
                </span>
                <span className="text-[11px] text-zinc-500">{x.order_kind}</span>
                <span className="ml-auto text-[11px] text-zinc-600">#{x.id}</span>
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className="rounded-lg bg-emerald-600/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
                  onClick={() => approve.mutate(x.id)}
                  disabled={approve.isPending}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-rose-600/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-500"
                  onClick={() => reject.mutate(x.id)}
                  disabled={reject.isPending}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
