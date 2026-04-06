import { fmt, useCancelOrder } from '../lib/api'
import type { Order } from '../lib/types'
import LoadingSkeleton from './LoadingSkeleton'

const statusStyle: Record<string, string> = {
  FILLED: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  PENDING: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  PARTIAL: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
  REJECTED: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
  CANCELLED: 'bg-zinc-500/10 text-zinc-500 border border-zinc-500/20',
}

export default function OrdersTable({
  orders,
  isLoading,
}: {
  orders: Order[] | undefined
  isLoading: boolean
}) {
  const cancel = useCancelOrder()

  return (
    <section>
      <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Recent Orders</h2>
      <div className="overflow-hidden rounded-xl border border-zinc-800/30 bg-zinc-900/20">
        {isLoading ? (
          <LoadingSkeleton rows={3} />
        ) : !orders || orders.length === 0 ? (
          <p className="p-6 text-center text-sm text-zinc-600">No orders yet</p>
        ) : (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-zinc-900/95 backdrop-blur-sm">
                <tr className="border-b border-zinc-800/30">
                  <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">ID</th>
                  <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Symbol</th>
                  <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Side</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Qty</th>
                  <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Status</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Limit</th>
                  <th className="px-4 py-3 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-t border-zinc-800/15 transition-colors hover:bg-zinc-800/15">
                    <td className="px-4 py-2.5 font-mono text-xs text-zinc-600">{o.id}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] font-semibold text-white">{o.symbol}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block rounded-lg px-2 py-0.5 text-[10px] font-bold ${
                          o.side === 'BUY'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}
                      >
                        {o.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[13px] text-zinc-300 tabular-nums">{o.quantity}</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-block rounded-lg px-2 py-0.5 text-[10px] font-bold ${statusStyle[o.status] ?? 'text-zinc-400'}`}>
                        {o.status}
                      </span>
                      {o.rejection_reason && (
                        <span className="ml-1.5 text-[10px] text-rose-500/60">({o.rejection_reason})</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[13px] text-zinc-500 tabular-nums">
                      {o.limit_price != null ? fmt(o.limit_price) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {(o.status === 'PENDING' || o.status === 'PARTIAL') && (
                        <button
                          type="button"
                          className="rounded-lg bg-zinc-800/40 border border-zinc-700/30 px-2.5 py-1 text-[10px] font-semibold text-zinc-400 transition-all hover:bg-zinc-700/40 hover:text-zinc-200"
                          onClick={() => cancel.mutate(o.id)}
                          disabled={cancel.isPending}
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
