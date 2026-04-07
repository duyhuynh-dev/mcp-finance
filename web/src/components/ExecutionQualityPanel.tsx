import { fmt, useExecutionQuality } from '../lib/api'

export default function ExecutionQualityPanel() {
  const { data, isPending } = useExecutionQuality(300)
  if (isPending || !data) {
    return (
      <section className="border-t border-zinc-800/30 pt-6">
        <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Execution Quality</h2>
        <p className="text-sm text-zinc-600">Loading execution quality…</p>
      </section>
    )
  }
  const s = data.summary
  return (
    <section className="border-t border-zinc-800/30 pt-6">
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Execution Quality v1</h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Orders analyzed" value={String(s.orders_analyzed)} />
        <Stat label="Fills analyzed" value={String(s.fills_analyzed)} />
        <Stat label="Notional" value={fmt(s.notional)} />
        <Stat label="Fees" value={fmt(s.fees)} />
        <Stat label="Fee bps" value={s.fee_bps_realized.toFixed(2)} />
        <Stat label="IS bps" value={s.implementation_shortfall_bps.toFixed(2)} />
      </div>
      <div className="mt-4 overflow-x-auto rounded-xl border border-zinc-800/30 bg-zinc-900/30">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800/30 text-zinc-500">
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-right">Fills</th>
              <th className="px-3 py-2 text-right">Notional</th>
              <th className="px-3 py-2 text-right">Fee bps</th>
              <th className="px-3 py-2 text-right">Avg buy</th>
              <th className="px-3 py-2 text-right">Avg sell</th>
              <th className="px-3 py-2 text-right">Net qty</th>
            </tr>
          </thead>
          <tbody>
            {data.by_symbol.map((r) => (
              <tr key={r.symbol} className="border-b border-zinc-800/15">
                <td className="px-3 py-2 font-mono text-zinc-200">{r.symbol}</td>
                <td className="px-3 py-2 text-right font-mono text-zinc-500">{r.fills}</td>
                <td className="px-3 py-2 text-right font-mono text-zinc-500">{fmt(r.notional)}</td>
                <td className="px-3 py-2 text-right font-mono text-zinc-500">{r.fee_bps_realized.toFixed(2)}</td>
                <td className="px-3 py-2 text-right font-mono text-zinc-500">{r.avg_buy_price?.toFixed(2) ?? '—'}</td>
                <td className="px-3 py-2 text-right font-mono text-zinc-500">{r.avg_sell_price?.toFixed(2) ?? '—'}</td>
                <td className="px-3 py-2 text-right font-mono text-zinc-500">{r.net_quantity.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/40 px-3.5 py-2.5">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-zinc-100">{value}</p>
    </div>
  )
}
