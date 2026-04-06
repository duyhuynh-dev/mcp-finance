import { useMetrics } from '../lib/api'
import ApiDisconnected from './ApiDisconnected'

export default function MetricsPanel() {
  const { data: m, isPending, isError, refetch } = useMetrics()

  if (isError) {
    return (
      <section>
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Observability</h2>
        <div className="mt-3">
          <ApiDisconnected refetch={() => refetch()} compact />
        </div>
      </section>
    )
  }

  if (isPending || !m) {
    return (
      <section>
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Observability</h2>
        <p className="mt-3 text-sm text-zinc-600">Loading metrics…</p>
      </section>
    )
  }

  return (
    <section className="border-t border-zinc-800/30 pt-6">
      <h2 className="mb-4 font-display text-sm font-bold tracking-tight text-white">Observability & Metrics</h2>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Uptime" value={`${Math.round(m.uptime_seconds)}s`} />
        <Stat label="Total Requests" value={String(m.total_requests)} />
        <Stat label="Errors" value={String(m.total_errors)} bad={m.total_errors > 0} />
        <Stat label="Error Rate" value={`${(m.error_rate * 100).toFixed(2)}%`} bad={m.error_rate > 0.01} />
        <Stat label="RPS" value={m.requests_per_second.toFixed(1)} />
        <Stat
          label="Status 2xx"
          value={String(
            Object.entries(m.status_codes)
              .filter(([k]) => k.startsWith('2'))
              .reduce((a, [, v]) => a + v, 0),
          )}
        />
        <Stat
          label="Status 4xx"
          value={String(
            Object.entries(m.status_codes)
              .filter(([k]) => k.startsWith('4'))
              .reduce((a, [, v]) => a + v, 0),
          )}
          bad
        />
        <Stat
          label="Status 5xx"
          value={String(
            Object.entries(m.status_codes)
              .filter(([k]) => k.startsWith('5'))
              .reduce((a, [, v]) => a + v, 0),
          )}
          bad
        />
      </div>

      {m.top_endpoints.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-widest text-zinc-600">Top Endpoints</h3>
          <div className="overflow-x-auto rounded-xl border border-zinc-800/30 bg-zinc-900/30">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800/30 text-[11px] uppercase tracking-widest text-zinc-600">
                  <th className="px-4 py-3 text-left">Path</th>
                  <th className="px-4 py-3 text-right">Hits</th>
                  <th className="px-4 py-3 text-right">Avg (ms)</th>
                  <th className="px-4 py-3 text-right">P95 (ms)</th>
                  <th className="px-4 py-3 text-right">Max (ms)</th>
                </tr>
              </thead>
              <tbody>
                {m.top_endpoints.map((ep) => {
                  const lat = m.latency[ep.path]
                  return (
                    <tr key={ep.path} className="border-b border-zinc-800/15 transition-colors hover:bg-zinc-800/20">
                      <td className="px-4 py-2.5 font-mono text-zinc-300">{ep.path}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-zinc-500">{ep.count}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-zinc-500">
                        {lat?.avg_ms.toFixed(1) ?? '–'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-zinc-500">
                        {lat?.p95_ms.toFixed(1) ?? '–'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-zinc-500">
                        {lat?.max_ms.toFixed(1) ?? '–'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-3 rounded-xl border border-zinc-800/20 bg-zinc-900/20 p-3">
        <p className="text-[11px] text-zinc-600">
          All responses include <code className="rounded bg-zinc-800/50 px-1 py-0.5 text-zinc-500">X-Request-Id</code>,{' '}
          <code className="rounded bg-zinc-800/50 px-1 py-0.5 text-zinc-500">X-Response-Time-Ms</code>, and{' '}
          <code className="rounded bg-zinc-800/50 px-1 py-0.5 text-zinc-500">X-RateLimit-*</code> headers.
        </p>
      </div>
    </section>
  )
}

function Stat({ label, value, bad }: { label: string; value: string; bad?: boolean }) {
  return (
    <div className="rounded-xl border border-zinc-800/30 bg-zinc-900/40 px-3.5 py-2.5">
      <p className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold ${bad ? 'text-rose-400' : 'text-zinc-100'}`}>
        {value}
      </p>
    </div>
  )
}
