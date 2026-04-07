import { useBrokerReconciliation } from '../lib/api'
import LoadingSkeleton from './LoadingSkeleton'

export default function ReconciliationPanel() {
  const { data, isPending } = useBrokerReconciliation()

  return (
    <section>
      <h2 className="mb-3 font-display text-sm font-bold tracking-tight text-white">
        Broker Reconciliation
      </h2>
      {isPending ? (
        <LoadingSkeleton rows={2} />
      ) : !data ? (
        <p className="py-4 text-sm text-zinc-600">No reconciliation data.</p>
      ) : !data.enabled ? (
        <p className="py-4 text-sm text-zinc-500">{data.reason ?? 'Reconciliation unavailable.'}</p>
      ) : data.error ? (
        <p className="py-4 text-sm text-rose-400">{data.error}</p>
      ) : (
        <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/30 p-4">
          <p className={`text-sm font-medium ${data.in_sync ? 'text-emerald-400' : 'text-amber-400'}`}>
            {data.in_sync ? 'Ledger and broker are in sync.' : 'Mismatches detected.'}
          </p>
          <div className="mt-3 space-y-1.5">
            {(data.mismatches ?? []).map((m) => (
              <div key={m.symbol} className="font-mono text-xs text-zinc-300">
                {m.symbol}: ledger {m.ledger_qty} vs broker {m.broker_qty} (delta {m.delta})
              </div>
            ))}
            {(data.mismatches ?? []).length === 0 && (
              <div className="font-mono text-xs text-zinc-500">No position deltas.</div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
