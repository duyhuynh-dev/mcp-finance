import { fmt, fmtPnl } from '../lib/api'
import type { PositionData } from '../lib/types'
import LoadingSkeleton from './LoadingSkeleton'

export default function PositionsTable({
  positions,
  isLoading,
}: {
  positions: Record<string, PositionData> | undefined
  isLoading: boolean
}) {
  const entries = Object.entries(positions ?? {})

  return (
    <section>
      <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Positions</h2>
      <div className="overflow-hidden rounded-xl border border-zinc-800/30 bg-zinc-900/20">
        {isLoading ? (
          <LoadingSkeleton rows={2} />
        ) : entries.length === 0 ? (
          <p className="p-6 text-center text-sm text-zinc-600">No open positions</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800/30">
                <th className="px-4 py-3 font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Symbol</th>
                <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Qty</th>
                <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Avg Cost</th>
                <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Mark</th>
                <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Mkt Value</th>
                <th className="px-4 py-3 text-right font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">P&L</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([sym, p]) => (
                <tr key={sym} className="border-t border-zinc-800/15 transition-colors hover:bg-zinc-800/15">
                  <td className="px-4 py-3 font-mono text-[13px] font-semibold text-white">{sym}</td>
                  <td className="px-4 py-3 text-right font-mono text-[13px] text-zinc-300 tabular-nums">{p.quantity}</td>
                  <td className="px-4 py-3 text-right font-mono text-[13px] text-zinc-500 tabular-nums">{fmt(p.avg_cost)}</td>
                  <td className="px-4 py-3 text-right font-mono text-[13px] text-zinc-300 tabular-nums">{fmt(p.mark_price)}</td>
                  <td className="px-4 py-3 text-right font-mono text-[13px] text-zinc-300 tabular-nums">{fmt(p.market_value)}</td>
                  <td
                    className={`px-4 py-3 text-right font-mono text-[13px] font-semibold tabular-nums ${
                      p.unrealized_pnl > 0.005
                        ? 'text-emerald-400'
                        : p.unrealized_pnl < -0.005
                          ? 'text-rose-400'
                          : 'text-zinc-500'
                    }`}
                  >
                    {fmtPnl(p.unrealized_pnl)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
