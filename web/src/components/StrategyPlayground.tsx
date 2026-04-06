import { useState } from 'react'
import { fmt, pct, useRunBacktest } from '../lib/api'
import type { BacktestResult } from '../lib/types'

interface Rule {
  type: 'buy_below' | 'sell_above'
  symbol: string
  threshold: number
  quantity: number
}

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'SPY', 'NVDA', 'AMZN', 'META', 'TSLA']

function n(v: number | null | undefined): string {
  const x = v ?? 0
  return x >= 9999 ? '∞' : x.toFixed(2)
}

export default function StrategyPlayground() {
  const run = useRunBacktest()
  const [rules, setRules] = useState<Rule[]>([
    { type: 'buy_below', symbol: 'AAPL', threshold: 175, quantity: 10 },
  ])
  const [config, setConfig] = useState({
    initial_cash: 100000,
    steps: 200,
    seed: 42,
    drift: 0.0005,
    volatility: 0.02,
  })
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState('')

  const addRule = () => {
    setRules([...rules, { type: 'buy_below', symbol: 'AAPL', threshold: 150, quantity: 10 }])
  }

  const removeRule = (idx: number) => {
    setRules(rules.filter((_, i) => i !== idx))
  }

  const updateRule = (idx: number, patch: Partial<Rule>) => {
    setRules(rules.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const handleRun = () => {
    if (rules.length === 0) return
    setError('')
    setResult(null)

    const syms = [...new Set(rules.map((r) => r.symbol))]
    const startPrices: Record<string, number> = {}
    const defaults: Record<string, number> = {
      AAPL: 180, MSFT: 380, GOOGL: 140, SPY: 500, NVDA: 700, AMZN: 180, META: 500, TSLA: 250,
    }
    for (const s of syms) startPrices[s] = defaults[s] ?? 100

    run.mutate(
      {
        name: 'playground',
        initial_cash: config.initial_cash,
        steps: config.steps,
        seed: config.seed,
        drift: config.drift,
        volatility: config.volatility,
        start_prices: startPrices,
        rules: rules.map((r) => ({
          type: r.type,
          symbol: r.symbol,
          threshold: r.threshold,
          quantity: r.quantity,
        })),
      },
      {
        onSuccess: (r) => setResult(r),
        onError: (e) => setError(e instanceof Error ? e.message : 'Failed'),
      },
    )
  }

  return (
    <section className="border-t border-zinc-800/30 pt-6">
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Strategy Playground</h2>

      <div className="mb-4 space-y-2">
        {rules.map((rule, idx) => (
          <div key={idx} className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-800/30 bg-zinc-900/30 px-4 py-2.5">
            <select
              className="glass-input rounded-lg px-2.5 py-1.5 text-sm text-zinc-100"
              value={rule.type}
              onChange={(e) => updateRule(idx, { type: e.target.value as Rule['type'] })}
            >
              <option value="buy_below">Buy Below</option>
              <option value="sell_above">Sell Above</option>
            </select>

            <select
              className="glass-input rounded-lg px-2.5 py-1.5 font-mono text-sm text-zinc-100"
              value={rule.symbol}
              onChange={(e) => updateRule(idx, { symbol: e.target.value })}
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-zinc-600">@</span>
              <input
                type="number"
                className="glass-input w-20 rounded-lg px-2.5 py-1.5 font-mono text-sm text-zinc-100"
                value={rule.threshold}
                onChange={(e) => updateRule(idx, { threshold: Number(e.target.value) })}
              />
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-zinc-600">qty</span>
              <input
                type="number"
                className="glass-input w-16 rounded-lg px-2.5 py-1.5 font-mono text-sm text-zinc-100"
                value={rule.quantity}
                onChange={(e) => updateRule(idx, { quantity: Number(e.target.value) })}
              />
            </div>

            <button
              onClick={() => removeRule(idx)}
              className="ml-auto rounded-md px-2 py-1 text-[11px] text-zinc-600 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
            >
              Remove
            </button>
          </div>
        ))}

        <button
          onClick={addRule}
          className="w-full rounded-xl border border-dashed border-zinc-800/40 py-2 text-xs text-zinc-600 transition-colors hover:border-zinc-600 hover:text-zinc-400"
        >
          + Add Rule
        </button>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Initial Cash" value={config.initial_cash} onChange={(v) => setConfig({ ...config, initial_cash: v })} />
        <Field label="Steps" value={config.steps} onChange={(v) => setConfig({ ...config, steps: v })} />
        <Field label="Seed" value={config.seed} onChange={(v) => setConfig({ ...config, seed: v })} />
        <Field label="Drift" value={config.drift} onChange={(v) => setConfig({ ...config, drift: v })} step={0.0001} />
        <Field label="Volatility" value={config.volatility} onChange={(v) => setConfig({ ...config, volatility: v })} step={0.005} />
        <button
          onClick={handleRun}
          disabled={run.isPending || rules.length === 0}
          className="rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-500 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/10 transition-all hover:shadow-indigo-500/20 hover:brightness-110 disabled:opacity-50"
        >
          {run.isPending ? 'Running…' : 'Run Backtest'}
        </button>
      </div>

      {error && <p className="mb-2 text-sm text-rose-400">{error}</p>}

      {result && (
        <div className="space-y-3">
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

          <svg viewBox="0 0 600 80" className="w-full">
            {(() => {
              const eq = result.equity_curve
              if (!eq || eq.length < 2) return null
              const mn = Math.min(...eq), mx = Math.max(...eq), rng = mx - mn || 1
              const pts = eq.map((v, i) => `${(i / (eq.length - 1)) * 600},${75 - ((v - mn) / rng) * 65}`).join(' ')
              return <polyline points={pts} fill="none" stroke="rgb(129 140 248)" strokeWidth="1.5" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            })()}
          </svg>
        </div>
      )}
    </section>
  )
}

function Field({ label, value, onChange, step }: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  return (
    <div>
      <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">{label}</label>
      <input
        type="number"
        step={step}
        className="glass-input w-24 rounded-lg px-2.5 py-2 font-mono text-sm text-zinc-100"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
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
