import { useState } from 'react'
import { useStrategySignals, useStrategies } from '../lib/api'
import ApiDisconnected from './ApiDisconnected'

const DIR_COLORS: Record<string, { badge: string; bar: string }> = {
  LONG: {
    badge: 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20',
    bar: 'bg-emerald-400',
  },
  SHORT: {
    badge: 'text-rose-400 bg-rose-500/10 border border-rose-500/20',
    bar: 'bg-rose-400',
  },
  FLAT: {
    badge: 'text-zinc-400 bg-zinc-500/10 border border-zinc-500/20',
    bar: 'bg-zinc-500',
  },
}

export default function SignalFeed() {
  const {
    data: strategiesData,
    isError: strategiesErr,
    refetch: refetchStrategies,
  } = useStrategies()
  const names = strategiesData?.strategies?.map((s) => s.name) ?? []
  const [filter, setFilter] = useState<string | undefined>(undefined)
  const {
    data,
    isPending: signalsPending,
    isError: signalsErr,
    refetch: refetchSignals,
  } = useStrategySignals(filter, 100)

  const signals = data?.signals ?? []
  const feedError = strategiesErr || signalsErr

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-sm font-bold tracking-tight text-white">Signal Feed</h3>
          <p className="mt-0.5 text-[11px] font-medium text-zinc-500">
            {signals.length} recent signals
          </p>
        </div>
        <select
          value={filter ?? ''}
          onChange={(e) => setFilter(e.target.value || undefined)}
          className="glass-input rounded-xl px-3.5 py-1.5 text-xs font-medium text-zinc-300"
        >
          <option value="">All strategies</option>
          {names.map((n) => (
            <option key={n} value={n}>{n.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {feedError ? (
        <ApiDisconnected
          refetch={() => {
            refetchStrategies()
            refetchSignals()
          }}
        />
      ) : signalsPending ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 rounded-xl" />
          ))}
        </div>
      ) : signals.length === 0 ? (
        <div className="glass rounded-xl p-10 text-center">
          <p className="text-sm font-medium text-zinc-600">
            No signals yet. Activate strategies and run the engine to generate signals.
          </p>
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
          {signals.map((sig, i) => {
            const c = DIR_COLORS[sig.direction] ?? DIR_COLORS.FLAT
            return (
              <div
                key={sig.id}
                className="glass group flex items-center gap-3 rounded-xl px-4 py-3 transition-all hover:border-zinc-600/40 animate-fade-in-up"
                style={{ animationDelay: `${i * 30}ms` }}
              >
                <span
                  className={`flex-shrink-0 rounded-lg px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] ${c.badge}`}
                >
                  {sig.direction}
                </span>

                <span className="font-mono text-[13px] font-bold text-white">
                  {sig.symbol}
                </span>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 max-w-[80px] overflow-hidden rounded-full bg-zinc-800/60">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${c.bar}`}
                        style={{ width: `${Math.round(sig.strength * 100)}%` }}
                      />
                    </div>
                    <span className="font-mono text-[10px] font-semibold text-zinc-500 tabular-nums">
                      {(sig.strength * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <span className="rounded-lg bg-zinc-800/40 border border-zinc-700/20 px-2 py-0.5 text-[10px] font-medium text-zinc-500 truncate max-w-[120px]">
                  {sig.strategy_name.replace(/_/g, ' ')}
                </span>

                <span className="font-mono text-[10px] text-zinc-600 flex-shrink-0 tabular-nums">
                  {new Date(sig.created_at).toLocaleTimeString()}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
