import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

const fmt = (n: number) =>
  new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(
    n,
  )

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

export default function App() {
  const qc = useQueryClient()
  const [depositAmt, setDepositAmt] = useState('25000')

  const portfolio = useQuery({
    queryKey: ['portfolio'],
    queryFn: () =>
      j<{
        cash: number
        equity: number
        trading_enabled: boolean
        positions: Record<string, { quantity: number }>
        rules: {
          version: string
          max_shares_per_symbol: number
          max_order_notional: number
          fee_bps: number
        }
      }>('/api/portfolio'),
  })

  const orders = useQuery({
    queryKey: ['orders'],
    queryFn: () => j<{ orders: Array<Record<string, unknown>> }>('/api/orders?limit=40'),
  })

  const fills = useQuery({
    queryKey: ['fills'],
    queryFn: () => j<{ fills: Array<Record<string, unknown>> }>('/api/fills?limit=40'),
  })

  const audit = useQuery({
    queryKey: ['audit'],
    queryFn: () => j<{ events: Array<Record<string, unknown>> }>('/api/audit?limit=60'),
  })

  const equitySeries = useQuery({
    queryKey: ['equity'],
    queryFn: () => j<{ points: Array<{ ts: string; equity: number }> }>('/api/equity-series?limit=300'),
  })

  const deposit = useMutation({
    mutationFn: (amount: number) => j('/api/deposit', { method: 'POST', body: JSON.stringify({ amount }) }),
    onSuccess: () => qc.invalidateQueries(),
  })

  const reset = useMutation({
    mutationFn: () => j('/api/reset-demo', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries(),
  })

  const toggleTrading = useMutation({
    mutationFn: (enabled: boolean) =>
      j('/api/trading-enabled', { method: 'POST', body: JSON.stringify({ enabled }) }),
    onSuccess: () => qc.invalidateQueries(),
  })

  const cancelOrder = useMutation({
    mutationFn: (orderId: number) =>
      j(`/api/cancel-order/${orderId}`, { method: 'POST', body: '{}' }),
    onSuccess: () => qc.invalidateQueries(),
  })

  const points = equitySeries.data?.points ?? []
  const lastEq = points.length ? points[points.length - 1].equity : portfolio.data?.equity

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-emerald-400/90">Paper desk</p>
            <h1 className="font-['IBM_Plex_Sans'] text-2xl font-semibold tracking-tight text-white">
              Finance Stack
            </h1>
            <p className="mt-1 max-w-xl text-sm text-zinc-400">
              MCP-gated ledger + policy. Dashboard reads the same SQLite as the portfolio MCP server.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="number"
              className="w-28 rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 font-mono text-sm text-zinc-100"
              value={depositAmt}
              onChange={(e) => setDepositAmt(e.target.value)}
            />
            <button
              type="button"
              className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
              onClick={() => deposit.mutate(Number(depositAmt))}
              disabled={deposit.isPending}
            >
              Deposit
            </button>
            <button
              type="button"
              className="rounded border border-zinc-600 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800"
              onClick={() => reset.mutate()}
              disabled={reset.isPending}
            >
              Reset demo
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-8">
        {portfolio.error && (
          <div className="rounded border border-amber-900/80 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
            API unreachable — start backend:{' '}
            <code className="font-mono text-amber-200">
              uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
            </code>
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Cash"
            value={portfolio.data ? fmt(portfolio.data.cash) : '—'}
            sub="USD"
          />
          <Stat
            label="Equity (MTM)"
            value={portfolio.data ? fmt(portfolio.data.equity) : '—'}
            sub={lastEq != null ? `last snap ${fmt(lastEq)}` : 'mock marks'}
          />
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Trading</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {portfolio.data?.trading_enabled ? (
                <span className="text-emerald-400">Enabled</span>
              ) : (
                <span className="text-rose-400">Kill switch</span>
              )}
            </p>
            <button
              type="button"
              className="mt-3 w-full rounded border border-zinc-600 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800"
              onClick={() => toggleTrading.mutate(!portfolio.data?.trading_enabled)}
              disabled={toggleTrading.isPending || !portfolio.data}
            >
              {portfolio.data?.trading_enabled ? 'Disable' : 'Enable'}
            </button>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Policy</p>
            <p className="mt-2 font-mono text-xs leading-relaxed text-zinc-300">
              v{portfolio.data?.rules.version ?? '—'} · max{' '}
              {portfolio.data?.rules.max_shares_per_symbol ?? '—'} sh/sym · max{' '}
              {portfolio.data ? fmt(portfolio.data.rules.max_order_notional) : '—'} / order · fee{' '}
              {portfolio.data?.rules.fee_bps ?? '—'} bps
            </p>
          </div>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <h2 className="text-sm font-semibold text-zinc-300">Equity (snapshots)</h2>
          <EquityChart points={points} />
        </section>

        <div className="grid gap-8 lg:grid-cols-2">
          <TableSection title="Positions" empty="No positions">
            {Object.entries(portfolio.data?.positions ?? {}).map(([sym, p]) => (
              <tr key={sym} className="border-t border-zinc-800">
                <td className="py-2 font-mono text-emerald-300">{sym}</td>
                <td className="py-2 text-right font-mono">{p.quantity}</td>
              </tr>
            ))}
          </TableSection>

          <TableSection title="Recent orders" empty="No orders">
            {(orders.data?.orders ?? []).map((o) => (
              <tr key={String(o.id)} className="border-t border-zinc-800">
                <td className="py-2 font-mono text-xs text-zinc-400">{String(o.client_order_id)}</td>
                <td className="py-2 font-mono">
                  {String(o.symbol)} {String(o.side)} {String(o.order_kind ?? '')}{' '}
                  <span className="text-zinc-500">{String(o.status)}</span>
                  {o.limit_price != null && (
                    <span className="text-zinc-600"> @ {fmt(Number(o.limit_price))}</span>
                  )}
                </td>
                <td className="py-2 text-right">
                  {String(o.status) === 'PENDING' && (
                    <button
                      type="button"
                      className="rounded border border-zinc-600 px-2 py-0.5 text-xs text-zinc-300 hover:bg-zinc-800"
                      onClick={() => cancelOrder.mutate(Number(o.id))}
                      disabled={cancelOrder.isPending}
                    >
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </TableSection>
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          <TableSection title="Fills" empty="No fills">
            {(fills.data?.fills ?? []).map((f) => (
              <tr key={String(f.id)} className="border-t border-zinc-800">
                <td className="py-2 font-mono text-xs">{String(f.symbol)}</td>
                <td className="py-2 text-right font-mono text-sm">
                  {String(f.quantity)} @ {fmt(Number(f.price))}
                  {f.fee != null && Number(f.fee) > 0 && (
                    <span className="block text-xs text-zinc-500">fee {fmt(Number(f.fee))}</span>
                  )}
                </td>
              </tr>
            ))}
          </TableSection>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-zinc-300">Audit trail</h2>
            <ul className="max-h-80 space-y-2 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/50 p-3 text-xs">
              {(audit.data?.events ?? []).map((e) => (
                <li key={String(e.id)} className="border-b border-zinc-800/80 pb-2 font-mono text-zinc-400">
                  <span className="text-emerald-500/90">{String(e.action)}</span> · {String(e.actor)}{' '}
                  <span className="text-zinc-600">{String(e.ts)}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </main>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-white">{value}</p>
      {sub && <p className="mt-1 text-xs text-zinc-500">{sub}</p>}
    </div>
  )
}

function TableSection({
  title,
  children,
  empty,
}: {
  title: string
  children: React.ReactNode
  empty: string
}) {
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-zinc-300">{title}</h2>
      <div className="overflow-hidden rounded-xl border border-zinc-800">
        <table className="w-full text-left text-sm">
          <tbody>
            {!children || (Array.isArray(children) && children.length === 0) ? (
              <tr>
                <td className="p-4 text-zinc-500">{empty}</td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function EquityChart({ points }: { points: Array<{ ts: string; equity: number }> }) {
  if (points.length < 2) {
    return <p className="py-8 text-center text-sm text-zinc-500">No snapshots yet — deposit and trade via MCP or script.</p>
  }
  const w = 800
  const h = 160
  const vals = points.map((p) => p.equity)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const pad = 8
  const x = (i: number) => (i / (points.length - 1)) * (w - pad * 2) + pad
  const y = (v: number) => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2)
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.equity)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full text-emerald-400/90">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
