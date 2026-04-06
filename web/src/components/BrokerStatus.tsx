import { useBrokerStatus } from '../lib/api'
import ApiDisconnected from './ApiDisconnected'

const fmt = (n: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(n)

export default function BrokerStatus() {
  const { data, isPending, isError, refetch } = useBrokerStatus()

  if (isError) {
    return (
      <section className="space-y-3">
        <h3 className="font-display text-sm font-bold tracking-tight text-white">
          Broker & Engine Status
        </h3>
        <ApiDisconnected refetch={() => refetch()} compact />
      </section>
    )
  }

  if (isPending) {
    return <section className="skeleton h-40 rounded-xl" />
  }

  if (!data) return null

  const { backend, broker, simulator_active, strategy_engine_running } = data

  const statusItems = [
    {
      label: 'Data Backend',
      value: backend,
      accent: 'indigo' as const,
      capitalize: true,
    },
    {
      label: 'Broker',
      connected: broker.connected,
      value: broker.connected ? 'Connected' : 'Disconnected',
      sub: broker.mode?.replace('_', ' '),
      error: broker.error,
      accent: broker.connected ? ('emerald' as const) : ('rose' as const),
    },
    {
      label: 'Strategy Engine',
      connected: strategy_engine_running,
      value: strategy_engine_running ? 'Active' : 'Idle',
      accent: strategy_engine_running ? ('emerald' as const) : (undefined as undefined),
    },
    {
      label: 'Price Simulator',
      connected: simulator_active,
      value: simulator_active ? 'Simulating' : 'Off',
      accent: simulator_active ? ('amber' as const) : (undefined as undefined),
    },
  ]

  const accentColors = {
    indigo: { bar: 'from-indigo-400 to-indigo-400/0', dot: 'bg-indigo-400' },
    emerald: { bar: 'from-emerald-400 to-emerald-400/0', dot: 'bg-emerald-400' },
    rose: { bar: 'from-rose-400 to-rose-400/0', dot: 'bg-rose-400' },
    amber: { bar: 'from-amber-400 to-amber-400/0', dot: 'bg-amber-400' },
  }

  return (
    <section className="space-y-4">
      <h3 className="font-display text-sm font-bold tracking-tight text-white">
        Broker & Engine Status
      </h3>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {statusItems.map((item) => {
          const c = item.accent ? accentColors[item.accent] : { bar: 'from-zinc-600/30 to-zinc-600/0', dot: 'bg-zinc-600' }
          return (
            <div key={item.label} className="glass relative overflow-hidden rounded-xl p-4 transition-all hover:border-zinc-600/40">
              <div className={`absolute left-0 top-0 h-full w-[2px] bg-gradient-to-b ${c.bar}`} />
              <div className="flex items-center gap-2 mb-2">
                <div className={`h-1.5 w-1.5 rounded-full ${c.dot} opacity-60`} />
                <p className="font-display text-[9px] font-bold uppercase tracking-[0.15em] text-zinc-500">
                  {item.label}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {item.connected !== undefined && (
                  <div
                    className={`h-2.5 w-2.5 rounded-full transition-colors ${
                      item.connected
                        ? `${c.dot} ${item.connected ? 'animate-pulse' : ''}`
                        : 'bg-zinc-600'
                    }`}
                  />
                )}
                <span
                  className={`font-display text-[15px] font-bold ${
                    item.accent === 'emerald' ? 'text-emerald-400'
                    : item.accent === 'rose' ? 'text-rose-400'
                    : 'text-white'
                  } ${item.capitalize ? 'capitalize' : ''}`}
                >
                  {item.value}
                </span>
              </div>
              {item.sub && (
                <p className="mt-1 font-display text-[10px] font-medium text-zinc-500 uppercase tracking-wider">
                  {item.sub}
                </p>
              )}
              {item.error && (
                <p className="mt-1 text-[10px] text-rose-400/80 truncate">{item.error}</p>
              )}
            </div>
          )
        })}
      </div>

      {broker.connected && broker.equity !== undefined && (
        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 opacity-60" />
            <p className="font-display text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500">
              Alpaca Paper Account
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="font-display text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Equity</p>
              <p className="mt-1 text-xl font-bold text-white font-mono tabular-nums">
                {fmt(broker.equity ?? 0)}
              </p>
            </div>
            <div>
              <p className="font-display text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Buying Power</p>
              <p className="mt-1 text-xl font-bold text-white font-mono tabular-nums">
                {fmt(broker.buying_power ?? 0)}
              </p>
            </div>
            <div>
              <p className="font-display text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Day Trades</p>
              <p className="mt-1 text-xl font-bold text-white font-mono tabular-nums">
                {broker.day_trade_count ?? 0}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
