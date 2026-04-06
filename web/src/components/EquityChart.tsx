import { useState } from 'react'
import { fmt } from '../lib/api'
import type { EquityPoint } from '../lib/types'
import LoadingSkeleton from './LoadingSkeleton'

export default function EquityChart({
  points,
  isLoading,
}: {
  points: EquityPoint[]
  isLoading: boolean
}) {
  const [hover, setHover] = useState<{ x: number; y: number; val: number; ts: string } | null>(
    null,
  )

  if (isLoading) {
    return (
      <section className="glass glow-emerald rounded-2xl p-6">
        <h2 className="font-display text-sm font-bold text-white">Equity Curve</h2>
        <LoadingSkeleton rows={2} />
      </section>
    )
  }

  if (points.length < 2) {
    return (
      <section className="glass glow-emerald rounded-2xl p-6">
        <h2 className="font-display text-sm font-bold text-white">Equity Curve</h2>
        <p className="py-10 text-center text-sm text-zinc-600">
          Deposit and trade to see your equity curve.
        </p>
      </section>
    )
  }

  const w = 800
  const h = 200
  const pad = { top: 24, right: 60, bottom: 32, left: 72 }
  const cw = w - pad.left - pad.right
  const ch = h - pad.top - pad.bottom

  const vals = points.map((p) => p.equity)
  let mn = Math.min(...vals)
  let mx = Math.max(...vals)
  const rawRange = mx - mn
  const minRange = Math.max(mx * 0.02, 100)
  if (rawRange < minRange) {
    const mid = (mx + mn) / 2
    mn = mid - minRange / 2
    mx = mid + minRange / 2
  }
  const range = mx - mn || 1

  const xPos = (i: number) => pad.left + (i / (points.length - 1)) * cw
  const yPos = (v: number) => pad.top + ch - ((v - mn) / range) * ch

  const linePath = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xPos(i)} ${yPos(p.equity)}`)
    .join(' ')

  const areaPath = `${linePath} L ${xPos(points.length - 1)} ${pad.top + ch} L ${xPos(0)} ${pad.top + ch} Z`

  const yTicks = 4
  const yLabels = Array.from({ length: yTicks + 1 }, (_, i) => mn + (range * i) / yTicks)

  const xTickCount = Math.min(5, points.length)
  const xIndices = Array.from({ length: xTickCount }, (_, i) =>
    Math.round((i * (points.length - 1)) / (xTickCount - 1)),
  )

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const mx2 = ((e.clientX - rect.left) / rect.width) * w
    const idx = Math.round(((mx2 - pad.left) / cw) * (points.length - 1))
    if (idx >= 0 && idx < points.length) {
      const pt = points[idx]
      setHover({ x: xPos(idx), y: yPos(pt.equity), val: pt.equity, ts: pt.ts })
    }
  }

  const latest = vals[vals.length - 1]
  const first = vals[0]
  const change = latest - first
  const changePct = ((change / first) * 100).toFixed(2)
  const isUp = change >= 0

  return (
    <section className="glass glow-emerald rounded-2xl p-6">
      <div className="mb-5 flex items-baseline justify-between">
        <div>
          <h2 className="font-display text-sm font-bold text-white">Equity Curve</h2>
          <p className="mt-1.5 text-[26px] font-bold tracking-tight text-white font-display tabular-nums">{fmt(latest)}</p>
        </div>
        <div className="text-right">
          <p className={`text-lg font-bold font-display tabular-nums ${isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isUp ? '+' : ''}{fmt(change)}
          </p>
          <p className={`text-xs font-semibold tabular-nums ${isUp ? 'text-emerald-400/60' : 'text-rose-400/60'}`}>
            {isUp ? '+' : ''}{changePct}%
          </p>
        </div>
      </div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="w-full"
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isUp ? 'rgb(52 211 153)' : 'rgb(251 113 133)'} stopOpacity="0.15" />
            <stop offset="100%" stopColor={isUp ? 'rgb(52 211 153)' : 'rgb(251 113 133)'} stopOpacity="0" />
          </linearGradient>
        </defs>

        {yLabels.map((v) => (
          <g key={v}>
            <line
              x1={pad.left}
              x2={w - pad.right}
              y1={yPos(v)}
              y2={yPos(v)}
              stroke="rgba(55, 60, 80, 0.25)"
              strokeWidth="0.5"
              strokeDasharray="4 6"
            />
            <text x={pad.left - 8} y={yPos(v) + 4} textAnchor="end" className="fill-zinc-600 text-[9px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {fmt(v)}
            </text>
          </g>
        ))}

        {xIndices.map((idx) => {
          const d = new Date(points[idx].ts)
          const label = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          return (
            <text
              key={idx}
              x={xPos(idx)}
              y={h - 6}
              textAnchor="middle"
              className="fill-zinc-600 text-[9px]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {label}
            </text>
          )
        })}

        <path d={areaPath} fill="url(#eqFill)" />
        <path
          d={linePath}
          fill="none"
          stroke={isUp ? 'rgb(52 211 153)' : 'rgb(251 113 133)'}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />

        {hover && (
          <>
            <line
              x1={hover.x}
              y1={pad.top}
              x2={hover.x}
              y2={pad.top + ch}
              stroke="rgba(129, 140, 248, 0.15)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <circle
              cx={hover.x}
              cy={hover.y}
              r="5"
              fill="#06070a"
              stroke={isUp ? 'rgb(52 211 153)' : 'rgb(251 113 133)'}
              strokeWidth="2"
            />
            <rect
              x={hover.x - 52}
              y={hover.y - 32}
              width="104"
              height="24"
              rx="8"
              fill="rgba(14, 16, 22, 0.95)"
              stroke="rgba(55, 60, 80, 0.4)"
              strokeWidth="0.5"
            />
            <text
              x={hover.x}
              y={hover.y - 16}
              textAnchor="middle"
              className="fill-white text-[10px]"
              style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
            >
              {fmt(hover.val)}
            </text>
          </>
        )}
      </svg>
    </section>
  )
}
