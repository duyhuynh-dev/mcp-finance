import { fmt, fmtPnl } from '../lib/api'
import type { Fill } from '../lib/types'
import LoadingSkeleton from './LoadingSkeleton'

export default function FillsTable({
  fills,
  isLoading,
}: {
  fills: Fill[] | undefined
  isLoading: boolean
}) {
  return (
    <section>
      <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Fills</h2>
      <div className="overflow-hidden rounded-xl border border-zinc-800/30 bg-zinc-900/20">
        {isLoading ? (
          <LoadingSkeleton rows={3} />
        ) : !fills || fills.length === 0 ? (
          <p className="p-6 text-center text-sm text-zinc-600">No fills yet</p>
        ) : (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-zinc-900/95 backdrop-blur-sm">
                <tr className="border-b border-zinc-800/30">
                  <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Symbol</th>
                  <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Side</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Qty</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Price</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Fee</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">P&L</th>
                  <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Time</th>
                </tr>
              </thead>
              <tbody>
                {fills.map((f) => (
                  <tr key={f.id} className="border-t border-zinc-800/15 transition-colors hover:bg-zinc-800/15">
                    <td className="px-4 py-2.5 font-mono text-[13px] font-semibold text-white">{f.symbol}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block rounded-lg px-2 py-0.5 text-[10px] font-bold ${
                          f.side === 'BUY'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}
                      >
                        {f.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[13px] text-zinc-300 tabular-nums">{f.quantity}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-[13px] text-zinc-300 tabular-nums">{fmt(f.price)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-[13px] text-zinc-500 tabular-nums">
                      {f.fee > 0.001 ? fmt(f.fee) : '—'}
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right font-mono text-[13px] tabular-nums ${
                        f.realized_pnl > 0.005
                          ? 'text-emerald-400'
                          : f.realized_pnl < -0.005
                            ? 'text-rose-400'
                            : 'text-zinc-600'
                      }`}
                    >
                      {Math.abs(f.realized_pnl) > 0.005 ? fmtPnl(f.realized_pnl) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[11px] text-zinc-600 tabular-nums">
                      {new Date(f.filled_at).toLocaleTimeString()}
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
