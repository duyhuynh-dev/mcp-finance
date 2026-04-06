import { useMemo } from 'react'
import { fmt, pct, useBacktestHistory } from '../lib/api'

function n(v: number | null | undefined): string {
  const x = v ?? 0
  return x >= 9999 ? '∞' : x.toFixed(2)
}

const COLORS = [
  'rgb(129 140 248)',
  'rgb(52 211 153)',
  'rgb(251 146 60)',
  'rgb(192 132 252)',
  'rgb(251 191 36)',
  'rgb(96 165 250)',
]

export default function ComparisonPanel() {
  const { data, isLoading } = useBacktestHistory()

  const runs = useMemo(() => {
    const all = data?.runs ?? []
    const seen = new Map<string, (typeof all)[0]>()
    for (const run of all) {
      if (!seen.has(run.name)) seen.set(run.name, run)
    }
    return [...seen.values()].slice(0, 6)
  }, [data])

  if (isLoading) {
    return (
      <section className="border-t border-zinc-800/30 pt-6">
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Portfolio Comparison</h2>
        <p className="mt-3 text-sm text-zinc-600">Loading…</p>
      </section>
    )
  }

  if (runs.length === 0) {
    return (
      <section className="border-t border-zinc-800/30 pt-6">
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Portfolio Comparison</h2>
        <p className="mt-3 text-sm text-zinc-600">
          Run backtests to see side-by-side comparisons.
        </p>
      </section>
    )
  }

  const allCurves = runs.map((r) => r.result.equity_curve ?? [])
  const flatVals = allCurves.flat()
  let globalMin = Math.min(...flatVals)
  let globalMax = Math.max(...flatVals)
  const rawRange = globalMax - globalMin
  const minRange = Math.max(globalMax * 0.05, 1000)
  if (rawRange < minRange) {
    const mid = (globalMax + globalMin) / 2
    globalMin = mid - minRange / 2
    globalMax = mid + minRange / 2
  }
  const range = globalMax - globalMin || 1
  const maxLen = Math.max(...allCurves.map((c) => c.length), 2)

  return (
    <section className="border-t border-zinc-800/30 pt-6">
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Portfolio Comparison</h2>

      <div className="mb-4 rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
        <svg viewBox="0 0 600 140" className="w-full">
          {runs.map((run, ci) => {
            const eq = run.result.equity_curve
            if (!eq || eq.length < 2) return null
            const pts = eq
              .map((v, i) => `${(i / (maxLen - 1)) * 600},${125 - ((v - globalMin) / range) * 110}`)
              .join(' ')
            return (
              <polyline
                key={run.id}
                points={pts}
                fill="none"
                stroke={COLORS[ci % COLORS.length]}
                strokeWidth="2"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
                opacity={0.85}
              />
            )
          })}
        </svg>

        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
          {runs.map((run, ci) => (
            <div key={run.id} className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: COLORS[ci % COLORS.length] }}
              />
              <span className="text-xs text-zinc-400">{run.name}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-800/30 bg-zinc-900/30">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800/30 text-[11px] uppercase tracking-widest text-zinc-600">
              <th className="px-4 py-3 text-left" />
              <th className="px-4 py-3 text-left">Name</th>
              <th className="px-4 py-3 text-right">Final Eq.</th>
              <th className="px-4 py-3 text-right">Return</th>
              <th className="px-4 py-3 text-right">Sharpe</th>
              <th className="px-4 py-3 text-right">Max DD</th>
              <th className="px-4 py-3 text-right">Win Rate</th>
              <th className="px-4 py-3 text-right">Trades</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run, ci) => {
              const r = run.result
              return (
                <tr key={run.id} className="border-b border-zinc-800/15 transition-colors hover:bg-zinc-800/20">
                  <td className="px-4 py-2.5">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: COLORS[ci % COLORS.length] }}
                    />
                  </td>
                  <td className="px-4 py-2.5 text-zinc-200">{run.name}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-zinc-300">{fmt(r.final_equity ?? 0)}</td>
                  <td className={`px-4 py-2.5 text-right font-mono ${(r.total_return_pct ?? 0) > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {pct(r.total_return_pct ?? 0)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-zinc-300">{n(r.sharpe_ratio)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-zinc-500">{pct(r.max_drawdown_pct ?? 0)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-zinc-300">{pct(r.win_rate ?? 0)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-zinc-500">{r.total_trades ?? 0}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
