/** Shown when API calls fail (e.g. backend not on :8001, Vite 502). */
export default function ApiDisconnected({
  refetch,
  compact,
}: {
  refetch?: () => void
  compact?: boolean
}) {
  return (
    <div
      className={`rounded-xl border border-amber-500/25 bg-amber-950/20 ${
        compact ? 'px-3 py-2 text-xs' : 'px-4 py-3 text-sm'
      } text-amber-100/90`}
    >
      <p className={`font-display font-semibold ${compact ? 'text-xs' : 'text-sm'}`}>
        Can’t reach the API (502 / connection refused)
      </p>
      <p className={`mt-1.5 text-zinc-500 ${compact ? 'text-[11px] leading-relaxed' : 'text-xs leading-relaxed'}`}>
        The UI proxies <code className="font-mono text-zinc-400">/api</code> to{' '}
        <code className="font-mono text-zinc-400">127.0.0.1:8001</code>. Start the backend from the repo root:
      </p>
      <pre
        className={`mt-2 overflow-x-auto rounded-lg bg-black/40 p-2 font-mono text-zinc-400 ${
          compact ? 'text-[10px]' : 'text-[11px]'
        }`}
      >
        {`set -a && source .env && set +a
export PYTHONPATH=packages/core
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload`}
      </pre>
      {refetch && (
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 text-xs font-semibold text-indigo-400 transition-colors hover:text-indigo-300"
        >
          Retry
        </button>
      )}
    </div>
  )
}
