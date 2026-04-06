import {
  useStrategies,
  useToggleStrategy,
  useRunStrategiesOnce,
  useStartStrategyEngine,
  useStopStrategyEngine,
  useBrokerStatus,
} from '../lib/api'
import ApiDisconnected from './ApiDisconnected'

export default function StrategyDashboard() {
  const { data, isPending, isError, refetch } = useStrategies()
  const toggle = useToggleStrategy()
  const runOnce = useRunStrategiesOnce()
  const startEngine = useStartStrategyEngine()
  const stopEngine = useStopStrategyEngine()
  const broker = useBrokerStatus()

  const strategies = data?.strategies ?? []
  const engineRunning = broker.data?.strategy_engine_running ?? false

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-sm font-bold tracking-tight text-white">
            Quant Strategies
          </h3>
          <p className="mt-0.5 text-[11px] font-medium text-zinc-500">
            {isPending
              ? 'Loading…'
              : `${strategies.length} registered · ${strategies.filter((s) => s.active).length} active`}
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => runOnce.mutate()}
            disabled={runOnce.isPending}
            className="btn-primary rounded-xl px-4 py-1.5 text-xs font-bold text-white disabled:opacity-50"
          >
            {runOnce.isPending ? 'Running…' : 'Run Once'}
          </button>
          {engineRunning ? (
            <button
              onClick={() => stopEngine.mutate()}
              disabled={stopEngine.isPending}
              className="btn-danger rounded-xl px-4 py-1.5 text-xs font-bold text-white disabled:opacity-50"
            >
              Stop Engine
            </button>
          ) : (
            <button
              onClick={() => startEngine.mutate()}
              disabled={startEngine.isPending}
              className="btn-success rounded-xl px-4 py-1.5 text-xs font-bold text-white disabled:opacity-50"
            >
              Start Engine
            </button>
          )}
          <div className="flex items-center gap-2 rounded-xl border border-zinc-800/30 bg-zinc-900/30 px-3 py-1.5">
            <div
              className={`h-2 w-2 rounded-full transition-colors ${
                engineRunning ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'
              }`}
            />
            <span className="font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">
              {engineRunning ? 'Running' : 'Stopped'}
            </span>
          </div>
        </div>
      </div>

      {isError ? (
        <ApiDisconnected refetch={() => refetch()} />
      ) : isPending ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-36 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {strategies.map((strat, i) => (
            <div
              key={strat.name}
              className={`glass group relative overflow-hidden rounded-xl p-5 transition-all duration-300 hover:border-zinc-600/40 animate-fade-in-up ${
                strat.active ? 'ring-1 ring-indigo-400/25 shadow-lg shadow-indigo-500/5' : ''
              }`}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div
                className={`absolute left-0 top-0 h-full w-[2px] bg-gradient-to-b ${
                  strat.active
                    ? 'from-emerald-400 to-emerald-400/0'
                    : 'from-zinc-600/30 to-zinc-600/0'
                }`}
              />

              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <p className="font-display text-[13px] font-bold text-white truncate capitalize">
                    {strat.name.replace(/_/g, ' ')}
                  </p>
                  <p className="mt-1 text-[11px] leading-relaxed text-zinc-500 line-clamp-2">
                    {strat.description}
                  </p>
                </div>
                <button
                  onClick={() => toggle.mutate(strat.name)}
                  disabled={toggle.isPending}
                  className={`ml-3 flex-shrink-0 rounded-lg px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.15em] transition-all border ${
                    strat.active
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25 hover:bg-emerald-500/20'
                      : 'bg-zinc-800/40 text-zinc-500 border-zinc-700/30 hover:bg-zinc-700/40 hover:text-zinc-300'
                  }`}
                >
                  {strat.active ? 'On' : 'Off'}
                </button>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {strat.universe.slice(0, 5).map((sym) => (
                  <span
                    key={sym}
                    className="rounded-md bg-zinc-800/50 border border-zinc-700/20 px-1.5 py-0.5 font-mono text-[9px] text-zinc-500"
                  >
                    {sym}
                  </span>
                ))}
                {strat.universe.length > 5 && (
                  <span className="rounded-md bg-zinc-800/50 border border-zinc-700/20 px-1.5 py-0.5 font-mono text-[9px] text-zinc-500">
                    +{strat.universe.length - 5}
                  </span>
                )}
              </div>

              <div className="mt-2.5 flex items-center gap-1.5">
                <div className="h-1 w-1 rounded-full bg-zinc-600 opacity-50" />
                <span className="font-display text-[10px] font-medium text-zinc-600">
                  lookback: {strat.required_history} bars
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
