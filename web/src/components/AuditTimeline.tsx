import { useState } from 'react'
import type { AuditEvent } from '../lib/types'
import LoadingSkeleton from './LoadingSkeleton'

function tryParse(s: string | null): unknown {
  if (!s) return null
  try {
    return JSON.parse(s)
  } catch {
    return s
  }
}

export default function AuditTimeline({
  events,
  isLoading,
}: {
  events: AuditEvent[] | undefined
  isLoading: boolean
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const toggle = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <section>
      <h2 className="font-display mb-3 text-sm font-bold tracking-tight text-white">Audit Trail</h2>
      <div className="max-h-96 overflow-y-auto rounded-xl border border-zinc-800/20 bg-zinc-900/20 p-4">
        {isLoading ? (
          <LoadingSkeleton rows={4} />
        ) : !events || events.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-600">No audit events</p>
        ) : (
          <ul className="space-y-1">
            {events.map((e) => {
              const isOpen = expanded.has(e.id)
              return (
                <li key={e.id} className="border-b border-zinc-800/20 pb-2">
                  <button
                    type="button"
                    className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-zinc-800/30"
                    onClick={() => toggle(e.id)}
                  >
                    <span className="shrink-0 rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-indigo-400">
                      {e.action}
                    </span>
                    <span className="text-zinc-500">{e.actor}</span>
                    <span className="ml-auto shrink-0 font-mono text-[11px] text-zinc-600">
                      {new Date(e.ts).toLocaleTimeString()}
                    </span>
                    <span className="text-zinc-600">{isOpen ? '−' : '+'}</span>
                  </button>
                  {isOpen && (
                    <div className="mt-1.5 ml-2 space-y-1.5 rounded-lg bg-zinc-950/40 p-3">
                      <div>
                        <span className="text-[11px] text-zinc-600">payload </span>
                        <pre className="inline whitespace-pre-wrap break-all font-mono text-[11px] text-zinc-400">
                          {JSON.stringify(tryParse(e.payload_json), null, 2)}
                        </pre>
                      </div>
                      {e.result_json && (
                        <div>
                          <span className="text-[11px] text-zinc-600">result </span>
                          <pre className="inline whitespace-pre-wrap break-all font-mono text-[11px] text-zinc-400">
                            {JSON.stringify(tryParse(e.result_json), null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}
