import { useState } from 'react'
import { usePlaceOrder } from '../lib/api'

let _seq = 0

export default function OrderEntryForm({ symbols }: { symbols: string[] }) {
  const placeOrder = usePlaceOrder()
  const [symbol, setSymbol] = useState(symbols[0] ?? 'AAPL')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [quantity, setQuantity] = useState('10')
  const [orderKind, setOrderKind] = useState<'MARKET' | 'LIMIT'>('MARKET')
  const [limitPrice, setLimitPrice] = useState('')
  const [msg, setMsg] = useState('')

  const submit = () => {
    _seq += 1
    const coid = `dash-${Date.now()}-${_seq}`
    placeOrder.mutate(
      {
        client_order_id: coid,
        symbol,
        side,
        quantity: Number(quantity),
        order_kind: orderKind,
        limit_price: orderKind === 'LIMIT' ? Number(limitPrice) : null,
      },
      {
        onSuccess: (data) => {
          const d = data as Record<string, unknown>
          setMsg(d.success ? `Order ${d.order_id} ${d.status}` : `Rejected: ${d.rejection_reason ?? d.message}`)
          setTimeout(() => setMsg(''), 4000)
        },
        onError: (e) => {
          setMsg(`Error: ${e.message}`)
          setTimeout(() => setMsg(''), 4000)
        },
      },
    )
  }

  return (
    <section className="glass rounded-2xl p-5">
      <h2 className="font-display mb-4 text-sm font-bold tracking-tight text-white">Place Order</h2>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1.5 block font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Symbol</label>
          <select
            className="glass-input rounded-xl px-3.5 py-2 font-mono text-sm text-zinc-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Side</label>
          <div className="flex overflow-hidden rounded-xl">
            {(['BUY', 'SELL'] as const).map((s) => (
              <button
                key={s}
                type="button"
                className={`px-4 py-2 text-sm font-semibold transition-all duration-200 ${
                  side === s
                    ? s === 'BUY'
                      ? 'btn-success text-white'
                      : 'btn-danger text-white'
                    : 'glass-input text-zinc-500 hover:text-zinc-300'
                }`}
                onClick={() => setSide(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1.5 block font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Qty</label>
          <input
            type="number"
            className="glass-input w-20 rounded-xl px-3 py-2 font-mono text-sm text-zinc-100 tabular-nums"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1.5 block font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Type</label>
          <select
            className="glass-input rounded-xl px-3.5 py-2 text-sm text-zinc-100"
            value={orderKind}
            onChange={(e) => setOrderKind(e.target.value as 'MARKET' | 'LIMIT')}
          >
            <option value="MARKET">Market</option>
            <option value="LIMIT">Limit</option>
          </select>
        </div>
        {orderKind === 'LIMIT' && (
          <div>
            <label className="mb-1.5 block font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Limit Price</label>
            <input
              type="number"
              step="0.01"
              className="glass-input w-24 rounded-xl px-3 py-2 font-mono text-sm text-zinc-100 tabular-nums"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
            />
          </div>
        )}
        <button
          type="button"
          className={`rounded-xl px-6 py-2 text-sm font-bold text-white transition-all duration-200 disabled:opacity-50 ${
            side === 'BUY' ? 'btn-success' : 'btn-danger'
          }`}
          onClick={submit}
          disabled={placeOrder.isPending}
        >
          {placeOrder.isPending ? 'Sending…' : `${side} ${symbol}`}
        </button>
      </div>
      {msg && (
        <div className="mt-3 rounded-xl bg-amber-500/10 border border-amber-500/20 px-4 py-2.5 animate-fade-in-up">
          <p className="text-xs font-semibold text-amber-300">{msg}</p>
        </div>
      )}
    </section>
  )
}
