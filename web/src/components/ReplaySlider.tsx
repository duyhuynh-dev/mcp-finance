import { useState } from 'react'
import { fmt, useEventTimeline, useReplay } from '../lib/api'

export default function ReplaySlider() {
  const { data: timeline } = useEventTimeline()
  const [sliderValue, setSliderValue] = useState<number | null>(null)
  const { data: state } = useReplay(sliderValue)

  const maxId = timeline?.max_event_id ?? 0
  const isActive = sliderValue !== null

  if (maxId === 0) {
    return (
      <section className="glass rounded-2xl p-5">
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Time Travel</h2>
        <p className="mt-4 text-center text-xs text-zinc-600">Trade to enable replay.</p>
      </section>
    )
  }

  return (
    <section className="glass rounded-2xl p-5" style={{ borderColor: isActive ? 'rgba(139, 92, 246, 0.3)' : undefined }}>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-sm font-bold tracking-tight text-white">Time Travel</h2>
        {isActive && (
          <button
            type="button"
            className="rounded-lg bg-violet-500/10 border border-violet-500/20 px-2.5 py-1 text-[10px] font-bold text-violet-300 transition-colors hover:bg-violet-500/20"
            onClick={() => setSliderValue(null)}
          >
            Back to live
          </button>
        )}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <span className="font-mono text-[10px] text-zinc-600">1</span>
        <input
          type="range"
          min={1}
          max={maxId}
          value={sliderValue ?? maxId}
          onChange={(e) => setSliderValue(Number(e.target.value))}
          className="flex-1 accent-violet-500"
        />
        <span className="font-mono text-[10px] text-zinc-600">{maxId}</span>
      </div>

      {state && isActive && (
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
          <div>
            <p className="text-zinc-600">Event #{state.event_id}</p>
            <p className="font-mono text-violet-300">{new Date(state.timestamp).toLocaleTimeString()}</p>
          </div>
          <div>
            <p className="text-zinc-600">Cash</p>
            <p className="font-mono text-zinc-200">{fmt(state.cash)}</p>
          </div>
          <div>
            <p className="text-zinc-600">Realized P&L</p>
            <p className="font-mono text-zinc-200">{fmt(state.realized_pnl)}</p>
          </div>
          <div>
            <p className="text-zinc-600">Orders / Fills</p>
            <p className="font-mono text-zinc-200">{state.total_orders} / {state.total_fills}</p>
          </div>
          {Object.keys(state.positions).length > 0 && (
            <div className="col-span-2">
              <p className="text-zinc-600">Positions</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(state.positions).map(([sym, qty]) => (
                  <span key={sym} className="rounded-md bg-violet-500/15 px-2 py-0.5 font-mono text-[11px] text-violet-300">
                    {sym}: {qty}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
