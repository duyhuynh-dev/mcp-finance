import { useState } from 'react'
import { fmt, pct, useRunBacktest } from '../lib/api'
import type { BacktestResult } from '../lib/types'

const PRESETS = [
  {
    label: 'AAPL Mean Reversion',
    config: {
      name: 'aapl_mean_reversion',
      initial_cash: 100000,
      steps: 200,
      seed: 42,
      drift: 0.0003,
      volatility: 0.015,
      start_prices: { AAPL: 180 },
      rules: [
        { type: 'buy_below', symbol: 'AAPL', threshold: 175, quantity: 20 },
        { type: 'sell_above', symbol: 'AAPL', threshold: 185, quantity: 20 },
      ],
    },
  },
  {
    label: 'Multi-Symbol Momentum',
    config: {
      name: 'multi_momentum',
      initial_cash: 200000,
      steps: 250,
      seed: 7,
      drift: 0.0005,
      volatility: 0.02,
      start_prices: { AAPL: 180, MSFT: 380 },
      rules: [
        { type: 'buy_below', symbol: 'AAPL', threshold: 170, quantity: 15 },
        { type: 'sell_above', symbol: 'AAPL', threshold: 190, quantity: 15 },
        { type: 'buy_below', symbol: 'MSFT', threshold: 370, quantity: 8 },
        { type: 'sell_above', symbol: 'MSFT', threshold: 395, quantity: 8 },
      ],
    },
  },
  {
    label: 'High Volatility Stress',
    config: {
      name: 'stress_test',
      initial_cash: 50000,
      steps: 300,
      seed: 99,
      drift: -0.001,
      volatility: 0.04,
      start_prices: { SPY: 500 },
      rules: [
        { type: 'buy_below', symbol: 'SPY', threshold: 480, quantity: 5 },
        { type: 'sell_above', symbol: 'SPY', threshold: 510, quantity: 5 },
      ],
    },
  },
]

function n(v: number | null | undefined): string {
  const x = v ?? 0
  return x >= 9999 ? '∞' : x.toFixed(2)
}

export default function BacktestPanel() {
  const run = useRunBacktest()
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState('')

  const launch = (config: Record<string, unknown>) => {
    setError('')
    setResult(null)
    run.mutate(config, {
      onSuccess: (r) => setResult(r),
      onError: (e) => setError(e instanceof Error ? e.message : 'Backtest failed'),
    })
  }

  return (
    <section>
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Preset Backtests</h2>

      <div className="mb-4 flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className="glass-input rounded-lg px-4 py-2 text-xs font-medium text-zinc-300 transition-all duration-200 hover:border-amber-500/40 hover:text-amber-300"
            onClick={() => launch(p.config)}
            disabled={run.isPending}
          >
            {p.label}
          </button>
        ))}
      </div>

      {run.isPending && <p className="text-sm text-amber-300 animate-pulse">Running backtest…</p>}
      {error && <p className="text-sm text-rose-400">{error}</p>}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Kv label="Final Equity" value={fmt(result.final_equity ?? 0)} />
            <Kv label="Return" value={pct(result.total_return_pct ?? 0)} good={(result.total_return_pct ?? 0) > 0} />
            <Kv label="Sharpe" value={n(result.sharpe_ratio)} good={(result.sharpe_ratio ?? 0) > 1} />
            <Kv label="Max DD" value={pct(result.max_drawdown_pct ?? 0)} />
            <Kv label="Trades" value={String(result.total_trades ?? 0)} />
            <Kv label="Win Rate" value={pct(result.win_rate ?? 0)} good={(result.win_rate ?? 0) > 0.5} />
            <Kv label="Profit Factor" value={n(result.profit_factor)} good={(result.profit_factor ?? 0) > 1} />
            <Kv label="Steps" value={String(result.steps ?? 0)} />
          </div>

          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-widest text-zinc-600">Equity curve</p>
            <svg viewBox="0 0 600 100" className="w-full">
              <defs>
                <linearGradient id="btFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(251 191 36)" stopOpacity="0.15" />
                  <stop offset="100%" stopColor="rgb(251 191 36)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {(() => {
                const eq = result.equity_curve
                if (eq.length < 2) return null
                const mn = Math.min(...eq)
                const mx = Math.max(...eq)
                const rng = mx - mn || 1
                const pts = eq
                  .map((v, i) => {
                    const x = (i / (eq.length - 1)) * 600
                    const y = 95 - ((v - mn) / rng) * 85
                    return `${x},${y}`
                  })
                  .join(' ')
                const area = `0,95 ${pts} 600,95`
                return (
                  <>
                    <polygon points={area} fill="url(#btFill)" />
                    <polyline points={pts} fill="none" stroke="rgb(251 191 36)" strokeWidth="1.5" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
                  </>
                )
              })()}
            </svg>
          </div>

          {Object.keys(result.price_history).length > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] uppercase tracking-widest text-zinc-600">Price paths</p>
              <svg viewBox="0 0 600 80" className="w-full">
                {Object.entries(result.price_history).map(([sym, prices], ci) => {
                  if (prices.length < 2) return null
                  const mn2 = Math.min(...prices)
                  const mx2 = Math.max(...prices)
                  const rng2 = mx2 - mn2 || 1
                  const colors = ['rgb(52 211 153)', 'rgb(96 165 250)', 'rgb(251 146 60)', 'rgb(192 132 252)']
                  const pts = prices
                    .map((p, i) => `${(i / (prices.length - 1)) * 600},${75 - ((p - mn2) / rng2) * 65}`)
                    .join(' ')
                  return (
                    <g key={sym}>
                      <polyline points={pts} fill="none" stroke={colors[ci % colors.length]} strokeWidth="1.2" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
                      <text x="4" y={12 + ci * 12} className="text-[9px]" fill={colors[ci % colors.length]}>
                        {sym}
                      </text>
                    </g>
                  )
                })}
              </svg>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function Kv({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/40 px-3.5 py-2.5">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className={`mt-0.5 font-mono text-sm font-semibold ${good === true ? 'text-emerald-400' : good === false ? 'text-rose-400' : 'text-zinc-200'}`}>
        {value}
      </p>
    </div>
  )
}
