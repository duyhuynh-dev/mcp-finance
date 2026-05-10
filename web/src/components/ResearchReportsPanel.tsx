import { type ReactNode, useEffect, useState } from 'react'
import {
  pct,
  useResearchRun,
  useResearchRuns,
  useRunWalkForwardResearch,
} from '../lib/api'
import type { ResearchMetrics } from '../lib/types'

const STRATEGIES = [
  'momentum',
  'mean_reversion',
  'pairs_trading',
  'portfolio_opt_max_sharpe',
  'portfolio_opt_risk_parity',
  'portfolio_opt_min_variance',
  'ml_alpha',
]

export default function ResearchReportsPanel() {
  const runs = useResearchRuns()
  const launch = useRunWalkForwardResearch()
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const detail = useResearchRun(selectedRunId)
  const [strategy, setStrategy] = useState('momentum')
  const [symbols, setSymbols] = useState('AAPL,MSFT,SPY,QQQ')
  const [totalBars, setTotalBars] = useState('360')
  const [trainBars, setTrainBars] = useState('120')
  const [testBars, setTestBars] = useState('40')
  const [seed, setSeed] = useState('42')

  useEffect(() => {
    if (!selectedRunId && runs.data?.runs[0]) {
      setSelectedRunId(runs.data.runs[0].id)
    }
  }, [runs.data?.runs, selectedRunId])

  const report = detail.data

  const run = () => {
    launch.mutate(
      {
        name: `${strategy}_${Date.now()}`,
        strategy_name: strategy,
        symbols: symbols.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean),
        total_bars: Number(totalBars),
        train_bars: Number(trainBars),
        test_bars: Number(testBars),
        step_bars: Number(testBars),
        seed: Number(seed),
        drift: 0.00025,
        volatility: 0.018,
        correlation: 0.35,
      },
      { onSuccess: (r) => setSelectedRunId(r.id) },
    )
  }

  return (
    <section className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-sm font-bold tracking-tight text-white">
            Strategy Research Reports
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Walk-forward validation with out-of-sample windows, benchmark comparison, exposure, turnover, and signal diagnostics.
          </p>
        </div>
        {report && (
          <span className="rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-bold text-indigo-300">
            {report.methodology.windows} windows
          </span>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-[1.2fr_1.2fr_repeat(4,minmax(0,0.55fr))_auto]">
        <Field label="Strategy">
          <select className="glass-input w-full rounded-lg px-2 py-2 text-sm text-zinc-100" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Universe">
          <input className="glass-input w-full rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" value={symbols} onChange={(e) => setSymbols(e.target.value)} />
        </Field>
        <NumberBox label="Bars" value={totalBars} setValue={setTotalBars} />
        <NumberBox label="Train" value={trainBars} setValue={setTrainBars} />
        <NumberBox label="Test" value={testBars} setValue={setTestBars} />
        <NumberBox label="Seed" value={seed} setValue={setSeed} />
        <div className="flex items-end">
          <button
            type="button"
            className="h-10 whitespace-nowrap rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 disabled:opacity-50"
            onClick={run}
            disabled={launch.isPending}
          >
            {launch.isPending ? 'Running...' : 'Run report'}
          </button>
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-600">Saved reports</p>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {(runs.data?.runs ?? []).map((r) => (
            <button
              key={r.id}
              type="button"
              className={`min-w-[15rem] rounded-lg border px-3 py-2 text-left ${
                selectedRunId === r.id
                  ? 'border-indigo-500/40 bg-indigo-500/10'
                  : 'border-zinc-800/30 bg-zinc-950/30 hover:border-zinc-700/60'
              }`}
              onClick={() => setSelectedRunId(r.id)}
            >
              <p className="truncate font-mono text-xs text-indigo-300">{r.name}</p>
              <p className="mt-1 text-[11px] text-zinc-500">
                {r.strategy_name} · Sharpe {r.metrics.sharpe?.toFixed(2) ?? '0.00'}
              </p>
            </button>
          ))}
          {!runs.data?.runs.length && <p className="py-3 text-sm text-zinc-600">No research reports yet.</p>}
        </div>
      </div>

      <div className="mt-4">
        {report ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Metric label="Strategy return" metric={report.metrics} field="total_return" good />
              <Metric label="Benchmark" metric={report.benchmark} field="total_return" />
              <Metric label="Excess Sharpe" value={report.excess.sharpe.toFixed(2)} good={report.excess.sharpe > 0} />
              <Metric label="Max drawdown" metric={report.metrics} field="max_drawdown" invert />
              <Metric label="Hit rate" metric={report.metrics} field="hit_rate" good />
              <Metric label="Turnover" value={(report.diagnostics.turnover ?? 0).toFixed(2)} />
              <Metric label="Avg exposure" value={pct(report.diagnostics.avg_abs_exposure ?? 0)} />
              <Metric label="Signals" value={String(totalSignals(report.diagnostics.signal_counts_by_symbol))} />
            </div>

            <Curve strategy={report.equity_curve} benchmark={report.benchmark_curve} />

            <div className="grid gap-3 xl:grid-cols-2">
              <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 p-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-600">Window validation</p>
                <div className="max-h-56 space-y-2 overflow-auto pr-1">
                  {report.windows.map((w) => (
                    <div key={w.index} className="rounded border border-zinc-800/30 bg-zinc-900/40 px-3 py-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-zinc-500">#{w.index}</span>
                        <span className="text-zinc-400">{w.test_start} to {w.test_end}</span>
                        <span className={`ml-auto font-mono ${w.metrics.total_return >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {pct(w.metrics.total_return)}
                        </span>
                      </div>
                      <p className="mt-1 text-zinc-600">signals {w.signal_count} · turnover {w.turnover.toFixed(2)} · sharpe {w.metrics.sharpe.toFixed(2)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 p-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-600">Diagnostics</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(report.diagnostics.signal_counts_by_symbol ?? {}).map(([sym, count]) => (
                    <span key={sym} className="rounded bg-indigo-500/10 px-2 py-1 font-mono text-[11px] text-indigo-300">{sym}: {count}</span>
                  ))}
                </div>
                <div className="mt-3 space-y-2">
                  {(report.diagnostics.latest_signals ?? []).slice(0, 5).map((s, i) => (
                    <div key={`${s.symbol}-${i}`} className="rounded border border-zinc-800/30 bg-zinc-900/40 px-3 py-2 text-xs">
                      <span className="font-mono text-zinc-300">{s.symbol}</span>
                      <span className="ml-2 text-zinc-500">{s.direction}</span>
                      <span className="ml-2 text-amber-300">{s.strength.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-zinc-600">Run or select a report.</p>
        )}
      </div>
    </section>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-600">
        {label}
      </span>
      {children}
    </label>
  )
}

function NumberBox({ label, value, setValue }: { label: string; value: string; setValue: (v: string) => void }) {
  return (
    <Field label={label}>
      <input aria-label={label} className="glass-input w-full rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" value={value} onChange={(e) => setValue(e.target.value)} />
    </Field>
  )
}

function totalSignals(x?: Record<string, number>) {
  return Object.values(x ?? {}).reduce((a, b) => a + b, 0)
}

function Metric({
  label,
  metric,
  field,
  value,
  good,
  invert,
}: {
  label: string
  metric?: ResearchMetrics
  field?: keyof ResearchMetrics
  value?: string
  good?: boolean
  invert?: boolean
}) {
  const raw = metric && field ? Number(metric[field]) : undefined
  const text = value ?? (field?.includes('return') || field?.includes('drawdown') || field === 'hit_rate' ? pct(raw ?? 0) : String(raw ?? '-'))
  const positive = raw != null && (invert ? raw < 0.1 : raw > 0)
  return (
    <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className={`mt-0.5 font-mono text-sm font-semibold ${good || positive ? 'text-emerald-300' : 'text-zinc-200'}`}>{text}</p>
    </div>
  )
}

function Curve({ strategy, benchmark }: { strategy: number[]; benchmark: number[] }) {
  const all = [...strategy, ...benchmark]
  const mn = Math.min(...all, 0.95)
  const mx = Math.max(...all, 1.05)
  const rng = mx - mn || 1
  const line = (arr: number[]) =>
    arr.map((v, i) => `${(i / Math.max(arr.length - 1, 1)) * 600},${95 - ((v - mn) / rng) * 85}`).join(' ')
  return (
    <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 p-3">
      <div className="mb-2 flex items-center gap-4 text-xs">
        <span className="flex items-center gap-2 text-emerald-300">
          <span className="h-0.5 w-5 rounded bg-emerald-400" />
          strategy
        </span>
        <span className="flex items-center gap-2 text-zinc-500">
          <span className="h-0.5 w-5 rounded bg-zinc-500" />
          benchmark
        </span>
      </div>
      <svg viewBox="0 0 600 105" className="w-full">
        <polyline points={line(benchmark)} fill="none" stroke="rgb(113 113 122)" strokeWidth="1.2" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        <polyline points={line(strategy)} fill="none" stroke="rgb(52 211 153)" strokeWidth="1.6" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  )
}
