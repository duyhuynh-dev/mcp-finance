import { fmt, pct, useRisk } from '../lib/api'
import LoadingSkeleton from './LoadingSkeleton'

export default function RiskPanel() {
  const { data: m, isLoading } = useRisk()

  if (isLoading) {
    return (
      <section>
        <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Risk Analytics</h2>
        <LoadingSkeleton rows={3} />
      </section>
    )
  }

  if (!m || (m.total_trades === 0 && m.equity_curve.length < 2)) {
    return (
      <section>
        <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Risk Analytics</h2>
        <p className="py-6 text-center text-sm text-zinc-600">
          Trade to generate risk metrics.
        </p>
      </section>
    )
  }

  const safe = (v: number | null | undefined) => v ?? 0
  const safeFmt = (v: number | null | undefined) => fmt(safe(v))
  const safePct = (v: number | null | undefined) => pct(safe(v))
  const safeFix = (v: number | null | undefined, d = 2) => {
    const n = safe(v)
    return n >= 9999 ? '∞' : n.toFixed(d)
  }

  const metrics = [
    { label: 'Sharpe Ratio', value: safeFix(m.sharpe_ratio), good: safe(m.sharpe_ratio) > 1 },
    { label: 'Total Return', value: safePct(m.total_return_pct), good: safe(m.total_return_pct) > 0 },
    { label: 'Volatility', value: safePct(m.annualized_volatility) },
    { label: 'Max Drawdown', value: safePct(m.max_drawdown_pct) },
    { label: 'VaR 95%', value: safeFmt(m.var_95) },
    { label: 'VaR 99%', value: safeFmt(m.var_99) },
    { label: 'Win Rate', value: safePct(m.win_rate), good: safe(m.win_rate) > 0.5 },
    { label: 'Profit Factor', value: safeFix(m.profit_factor), good: safe(m.profit_factor) > 1 },
    { label: 'Total Trades', value: String(m.total_trades ?? 0) },
    { label: 'Best Day', value: safePct(m.best_day_pct), good: true },
    { label: 'Worst Day', value: safePct(m.worst_day_pct) },
    { label: 'Avg Win / Loss', value: `${safeFmt(m.avg_win)} / ${safeFmt(m.avg_loss)}` },
  ]

  const ddCurve = m.drawdown_curve
  const hasDd = ddCurve.length > 1

  return (
    <section>
      <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Risk Analytics</h2>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {metrics.map((m2) => (
          <div key={m2.label} className="rounded-xl border border-zinc-800/20 bg-zinc-900/30 px-3.5 py-3 transition-colors hover:bg-zinc-800/20">
            <p className="font-display text-[9px] font-bold uppercase tracking-[0.15em] text-zinc-500">{m2.label}</p>
            <p className={`mt-1 font-mono text-sm font-bold tabular-nums ${m2.good ? 'text-emerald-400' : 'text-zinc-200'}`}>
              {m2.value}
            </p>
          </div>
        ))}
      </div>

      {hasDd && (
        <div className="mt-4">
          <p className="mb-1.5 font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">Drawdown curve</p>
          <svg viewBox="0 0 400 60" className="w-full">
            <defs>
              <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(244 63 94)" stopOpacity="0.2" />
                <stop offset="100%" stopColor="rgb(244 63 94)" stopOpacity="0" />
              </linearGradient>
            </defs>
            {(() => {
              const mx = Math.max(...ddCurve, 0.001)
              const pts = ddCurve
                .map((d, i) => {
                  const x = (i / (ddCurve.length - 1)) * 400
                  const y = 60 - (d / mx) * 55
                  return `${x},${y}`
                })
                .join(' ')
              const area = `0,60 ${pts} 400,60`
              return (
                <>
                  <polygon points={area} fill="url(#ddFill)" />
                  <polyline points={pts} fill="none" stroke="rgb(244 63 94)" strokeWidth="1.5" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
                </>
              )
            })()}
          </svg>
        </div>
      )}

      {Object.keys(m.correlation_matrix).length > 1 && (
        <div className="mt-4">
          <p className="mb-1.5 font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">Correlation matrix</p>
          <div className="overflow-x-auto">
            <table className="text-xs">
              <thead>
                <tr>
                  <th className="px-2.5 py-1.5 text-zinc-600"></th>
                  {Object.keys(m.correlation_matrix).map((s) => (
                    <th key={s} className="px-2.5 py-1.5 font-mono text-zinc-500">{s}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(m.correlation_matrix).map(([row, cols]) => (
                  <tr key={row}>
                    <td className="px-2.5 py-1.5 font-mono text-zinc-500">{row}</td>
                    {Object.values(cols).map((v, i) => (
                      <td
                        key={i}
                        className={`px-2.5 py-1.5 text-center font-mono ${
                          v > 0.5 ? 'text-emerald-400' : v < -0.5 ? 'text-rose-400' : 'text-zinc-600'
                        }`}
                      >
                        {v.toFixed(2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
