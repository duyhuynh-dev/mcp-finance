import { type ReactNode, useState } from 'react'
import {
  fmt,
  pct,
  useAgents,
  useCreateAgentOrderIntent,
  useRiskWhatIf,
} from '../lib/api'

let seq = 0

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'SPY', 'NVDA', 'AMZN', 'META', 'TSLA', 'QQQ', 'AMD']

export default function TradeDecisionPanel() {
  const agents = useAgents()
  const whatIf = useRiskWhatIf()
  const createIntent = useCreateAgentOrderIntent()
  const [agentId, setAgentId] = useState('')
  const [symbol, setSymbol] = useState('AAPL')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [quantity, setQuantity] = useState('25')
  const [orderKind, setOrderKind] = useState<'MARKET' | 'LIMIT'>('MARKET')
  const [limitPrice, setLimitPrice] = useState('')
  const [message, setMessage] = useState('')

  const selectedAgentId = agentId ? Number(agentId) : null
  const decision = whatIf.data

  const body = () => ({
    symbol,
    side,
    quantity: Number(quantity),
    order_kind: orderKind,
    limit_price: orderKind === 'LIMIT' ? Number(limitPrice) : null,
    agent_id: selectedAgentId,
    tool: 'place_order',
  })

  const runDecision = () => whatIf.mutate(body())

  const propose = () => {
    if (!selectedAgentId || !decision) return
    seq += 1
    createIntent.mutate(
      {
        client_order_id: `agent-proposal-${Date.now()}-${seq}`,
        symbol,
        side,
        quantity: Number(quantity),
        order_kind: orderKind,
        limit_price: orderKind === 'LIMIT' ? Number(limitPrice) : null,
        agent_id: selectedAgentId,
      },
      {
        onSuccess: () => {
          setMessage('Proposal queued for human review.')
          setTimeout(() => setMessage(''), 3500)
        },
        onError: (e) => {
          setMessage(`Proposal failed: ${e.message}`)
          setTimeout(() => setMessage(''), 4500)
        },
      },
    )
  }

  return (
    <section className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-sm font-bold tracking-tight text-white">Trade Decision Engine</h2>
          <p className="mt-1 text-xs text-zinc-500">Pre-trade controls for agent proposals before money moves.</p>
        </div>
        {decision && <DecisionPill decision={decision.decision ?? (decision.allowed ? 'ALLOW' : 'REJECT')} />}
      </div>

      <div className="rounded-xl border border-zinc-800/30 bg-zinc-950/30 p-3">
        <div className="grid gap-2 md:grid-cols-6">
          <Field label="Requester" wide>
            <select className="glass-input w-full rounded-lg px-2 py-2 text-sm text-zinc-100" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
              <option value="">Human dashboard</option>
              {agents.data?.agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Symbol">
            <select className="glass-input w-full rounded-lg px-2 py-2 text-sm text-zinc-100" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Side">
            <select className="glass-input w-full rounded-lg px-2 py-2 text-sm text-zinc-100" value={side} onChange={(e) => setSide(e.target.value as 'BUY' | 'SELL')}>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </Field>
          <Field label="Quantity">
            <input className="glass-input w-full rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </Field>
          <Field label="Order">
            <select className="glass-input w-full rounded-lg px-2 py-2 text-sm text-zinc-100" value={orderKind} onChange={(e) => setOrderKind(e.target.value as 'MARKET' | 'LIMIT')}>
              <option value="MARKET">Market</option>
              <option value="LIMIT">Limit</option>
            </select>
          </Field>
        </div>

        {orderKind === 'LIMIT' && (
          <Field label="Limit price">
            <input className="glass-input mt-2 w-36 rounded-lg px-2 py-2 font-mono text-sm text-zinc-100" type="number" step="0.01" value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} placeholder="Limit price" />
          </Field>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/20 disabled:opacity-50" onClick={runDecision} disabled={whatIf.isPending || !Number(quantity)}>
            {whatIf.isPending ? 'Evaluating...' : 'Evaluate risk'}
          </button>
          <button type="button" className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 disabled:opacity-50" onClick={propose} disabled={!selectedAgentId || !decision || decision.decision === 'REJECT' || createIntent.isPending}>
            {createIntent.isPending ? 'Queuing...' : 'Queue for approval'}
          </button>
        </div>
      </div>

      {message && <p className="mt-3 text-xs font-semibold text-amber-300">{message}</p>}

      {decision && (
        <div className="mt-4 space-y-3">
          <DecisionSummary decision={decision.decision ?? (decision.allowed ? 'ALLOW' : 'REJECT')} reason={decision.reason ?? 'none'} />
          <div className="grid gap-3 lg:grid-cols-[0.85fr_1.15fr]">
            <div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-600">Trade impact</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <Kv label="Notional" value={fmt(decision.projected_notional ?? 0)} />
                <Kv label="Fill / fee" value={`${fmt(decision.estimated_fill_price ?? 0)} / ${fmt(decision.estimated_fee ?? 0)}`} />
                <Kv label="Position" value={`${decision.current_position ?? 0} -> ${decision.projected_position ?? 0}`} />
                <Kv label="Gross multiple" value={decision.projected_gross_multiple_after?.toFixed(4) ?? '-'} />
                <Kv label="Concentration" value={decision.projected_concentration_after != null ? pct(decision.projected_concentration_after) : '-'} />
                <Kv label="Agent" value={decision.agent?.name ?? decision.actor ?? 'human'} />
              </div>
            </div>
            <div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-600">Control checks</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {(decision.checks ?? []).map((check) => (
                  <div key={check.name} className={`rounded-lg border px-3 py-2 ${check.passed ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-rose-500/25 bg-rose-500/5'}`}>
                    <p className={`text-xs font-semibold ${check.passed ? 'text-emerald-300' : 'text-rose-300'}`}>{check.name.replace(/_/g, ' ')}</p>
                    <p className="mt-1 truncate font-mono text-[11px] text-zinc-500">{JSON.stringify(check.detail)}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function Field({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={wide ? 'md:col-span-2' : undefined}>
      <span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-600">{label}</span>
      {children}
    </label>
  )
}

function DecisionSummary({ decision, reason }: { decision: string; reason: string }) {
  const cls =
    decision === 'REJECT'
      ? 'border-rose-500/25 bg-rose-500/5 text-rose-300'
      : decision === 'REQUIRE_APPROVAL'
        ? 'border-amber-500/25 bg-amber-500/5 text-amber-300'
        : decision === 'RESIZE'
          ? 'border-indigo-500/25 bg-indigo-500/5 text-indigo-300'
          : 'border-emerald-500/25 bg-emerald-500/5 text-emerald-300'
  return (
    <div className={`rounded-xl border px-4 py-3 ${cls}`}>
      <p className="text-[10px] font-bold uppercase tracking-widest opacity-80">Decision</p>
      <div className="mt-1 flex flex-wrap items-end justify-between gap-2">
        <p className="font-display text-2xl font-bold tracking-tight">{decision}</p>
        <p className="max-w-xl truncate font-mono text-xs text-zinc-400">{reason}</p>
      </div>
    </div>
  )
}

function DecisionPill({ decision }: { decision: string }) {
  const cls =
    decision === 'REJECT'
      ? 'bg-rose-500/15 text-rose-300'
      : decision === 'REQUIRE_APPROVAL'
        ? 'bg-amber-500/15 text-amber-300'
        : decision === 'RESIZE'
          ? 'bg-indigo-500/15 text-indigo-300'
          : 'bg-emerald-500/15 text-emerald-300'
  return <span className={`rounded-full px-3 py-1 text-xs font-bold ${cls}`}>{decision}</span>
}

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800/30 bg-zinc-950/30 px-3 py-2">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className="mt-0.5 truncate font-mono text-xs text-zinc-200">{value}</p>
    </div>
  )
}
