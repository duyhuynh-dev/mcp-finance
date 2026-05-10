import { useState } from 'react'
import { fmt, useSubmitVenueOrder, useTickVenue, useVenueOrders, useVenueStatus } from '../lib/api'

let seq = 0

export default function VenuePanel() {
  const status = useVenueStatus()
  const orders = useVenueOrders()
  const submit = useSubmitVenueOrder()
  const tick = useTickVenue()
  const [symbol, setSymbol] = useState('AAPL')
  const [quantity, setQuantity] = useState('75')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [type, setType] = useState<'MARKET' | 'LIMIT'>('MARKET')
  const [limit, setLimit] = useState('')

  const send = () => {
    seq += 1
    submit.mutate({
      client_order_id: `venue-ui-${Date.now()}-${seq}`,
      symbol,
      side,
      quantity: Number(quantity),
      order_type: type,
      limit_price: type === 'LIMIT' ? Number(limit) : null,
      depth_per_tick: 40,
      latency_ticks: 1,
    })
  }

  const s = status.data
  const recent = orders.data?.orders.slice(0, 8) ?? []

  return (
    <section className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-sm font-bold tracking-tight text-white">Simulated Execution Venue</h2>
          <p className="mt-1 text-xs text-zinc-500">Spread, market impact, latency, partial fills, expiry, and ledger mirroring.</p>
        </div>
        <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-300">
          {s?.mode ?? 'simulated'}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
        <Stat label="Fills" value={String(s?.fills.count ?? 0)} />
        <Stat label="Quantity" value={(s?.fills.quantity ?? 0).toFixed(2)} />
        <Stat label="Spread" value={`${(s?.fills.avg_spread_bps ?? 0).toFixed(2)} bps`} />
        <Stat label="Impact" value={`${(s?.fills.avg_impact_bps ?? 0).toFixed(2)} bps`} />
        <Stat label="Open" value={String((s?.orders_by_status.OPEN ?? 0) + (s?.orders_by_status.PARTIAL ?? 0))} />
      </div>

      <div className="grid gap-2 md:grid-cols-7">
        <input className="glass-input rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
        <select className="glass-input rounded-lg px-2 py-2 text-sm text-zinc-100" value={side} onChange={(e) => setSide(e.target.value as 'BUY' | 'SELL')}>
          <option value="BUY">BUY</option>
          <option value="SELL">SELL</option>
        </select>
        <input className="glass-input rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <select className="glass-input rounded-lg px-2 py-2 text-sm text-zinc-100" value={type} onChange={(e) => setType(e.target.value as 'MARKET' | 'LIMIT')}>
          <option value="MARKET">Market</option>
          <option value="LIMIT">Limit</option>
        </select>
        <input className="glass-input rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" type="number" placeholder="limit" value={limit} onChange={(e) => setLimit(e.target.value)} disabled={type === 'MARKET'} />
        <button type="button" className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/20 disabled:opacity-50" onClick={send} disabled={submit.isPending || !Number(quantity)}>
          Submit
        </button>
        <button type="button" className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 disabled:opacity-50" onClick={() => tick.mutate()} disabled={tick.isPending}>
          Tick venue
        </button>
      </div>

      <div className="mt-4 space-y-2">
        {recent.map((o) => (
          <div key={o.id} className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-mono text-zinc-500">#{o.id}</span>
              <span className="text-zinc-200">{o.symbol} {o.side} {o.quantity}</span>
              <span className={`rounded px-2 py-0.5 font-semibold ${tone(o.status)}`}>{o.status}</span>
              <span className="ml-auto font-mono text-zinc-500">{o.filled_quantity}/{o.quantity} @ {o.avg_fill_price ? fmt(o.avg_fill_price) : '-'}</span>
            </div>
            {o.fills.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {o.fills.map((f) => (
                  <span key={f.id} className="rounded bg-zinc-800/60 px-2 py-0.5 font-mono text-[11px] text-zinc-400">
                    t{f.tick}: {f.quantity} @ {fmt(f.price)}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {!recent.length && <p className="py-4 text-sm text-zinc-600">No venue orders yet.</p>}
      </div>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold text-zinc-200">{value}</p>
    </div>
  )
}

function tone(status: string) {
  if (status === 'FILLED') return 'bg-emerald-500/10 text-emerald-300'
  if (status === 'PARTIAL') return 'bg-amber-500/10 text-amber-300'
  if (status === 'CANCELLED' || status === 'EXPIRED' || status === 'REJECTED') return 'bg-rose-500/10 text-rose-300'
  return 'bg-indigo-500/10 text-indigo-300'
}
