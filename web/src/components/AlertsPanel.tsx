import { useState } from 'react'
import { useAlerts, useAlertNotifications, useCreateAlert, useDeleteAlert, useEvaluateAlerts } from '../lib/api'
import ApiDisconnected from './ApiDisconnected'

const ALERT_TYPES = [
  { value: 'drawdown_above', label: 'Drawdown Above %' },
  { value: 'pnl_below', label: 'P&L Below $' },
  { value: 'concentration_above', label: 'Concentration Above %' },
  { value: 'equity_below', label: 'Equity Below $' },
  { value: 'equity_above', label: 'Equity Above $' },
  { value: 'loss_streak', label: 'Loss Streak >= N' },
]

export default function AlertsPanel() {
  const { data: alertsData, isPending, isError, refetch } = useAlerts()
  const { data: notifData } = useAlertNotifications()
  const create = useCreateAlert()
  const del = useDeleteAlert()
  const evaluate = useEvaluateAlerts()

  const [name, setName] = useState('')
  const [type, setType] = useState('drawdown_above')
  const [threshold, setThreshold] = useState(0.1)
  const [symbol, setSymbol] = useState('')

  const handleCreate = () => {
    if (!name.trim()) return
    create.mutate(
      {
        name: name.trim(),
        alert_type: type,
        threshold,
        symbol: symbol.trim().toUpperCase() || null,
      },
      { onSuccess: () => { setName(''); setThreshold(0.1) } },
    )
  }

  const rules = alertsData?.rules ?? []
  const notifications = notifData?.notifications ?? []

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Alert Rules</h2>
        <button
          onClick={() => evaluate.mutate()}
          disabled={evaluate.isPending}
          className="rounded-lg bg-amber-600/80 px-3 py-1.5 text-[11px] font-medium text-white transition-all hover:bg-amber-500 disabled:opacity-50"
        >
          {evaluate.isPending ? 'Evaluating…' : 'Evaluate Now'}
        </button>
      </div>

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Name</label>
          <input
            className="glass-input rounded-lg px-3 py-2 text-sm text-zinc-100"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="High drawdown"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Type</label>
          <select
            className="glass-input rounded-lg px-3 py-2 text-sm text-zinc-100"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {ALERT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Threshold</label>
          <input
            type="number"
            step={type.includes('pct') || type.includes('above') && !type.includes('equity') ? 0.01 : 1}
            className="glass-input w-24 rounded-lg px-3 py-2 font-mono text-sm text-zinc-100"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-zinc-600">Symbol</label>
          <input
            className="glass-input w-20 rounded-lg px-3 py-2 font-mono text-sm text-zinc-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="opt."
          />
        </div>
        <button
          onClick={handleCreate}
          disabled={create.isPending || !name.trim()}
          className="rounded-lg bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/10 transition-all hover:shadow-blue-500/20 hover:brightness-110 disabled:opacity-50"
        >
          Create
        </button>
      </div>

      {isError ? (
        <ApiDisconnected refetch={() => refetch()} compact />
      ) : isPending ? (
        <p className="text-sm text-zinc-600">Loading…</p>
      ) : rules.length > 0 ? (
        <div className="mb-4 overflow-x-auto rounded-xl border border-zinc-800/30 bg-zinc-900/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800/30 text-[11px] uppercase tracking-widest text-zinc-600">
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Threshold</th>
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b border-zinc-800/15 transition-colors hover:bg-zinc-800/20">
                  <td className="px-4 py-2.5 text-zinc-200">{r.name}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-zinc-500">{r.alert_type}</td>
                  <td className="px-4 py-2.5 font-mono text-zinc-300">{r.threshold}</td>
                  <td className="px-4 py-2.5 text-zinc-500">{r.symbol ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => del.mutate(r.id)}
                      className="rounded-md px-2 py-1 text-[11px] text-zinc-600 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-4 text-sm text-zinc-600">No alert rules configured.</p>
      )}

      {notifications.length > 0 && (
        <div>
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-widest text-zinc-600">Recent Notifications</h3>
          <div className="max-h-48 space-y-1.5 overflow-y-auto">
            {notifications.map((notif) => (
              <div
                key={notif.id}
                className={`rounded-lg px-3.5 py-2.5 text-xs ${
                  notif.severity === 'critical'
                    ? 'border border-rose-500/20 bg-rose-950/20 text-rose-300'
                    : notif.severity === 'warning'
                      ? 'border border-amber-500/20 bg-amber-950/15 text-amber-300'
                      : 'border border-zinc-800/30 bg-zinc-900/30 text-zinc-400'
                }`}
              >
                <span className="font-medium">{notif.alert_name}</span>
                <span className="mx-2 text-zinc-600">·</span>
                {notif.message}
                <span className="ml-2 font-mono text-zinc-600">{notif.fired_at.slice(11, 19)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
