import { useState } from 'react'
import { useDeposit, useResetDemo } from '../lib/api'

export default function Header() {
  const [depositAmt, setDepositAmt] = useState('25000')
  const deposit = useDeposit()
  const reset = useResetDemo()

  const nudge = (delta: number) => {
    const next = Math.max(0, (Number(depositAmt) || 0) + delta)
    setDepositAmt(String(next))
  }

  return (
    <header className="sticky top-0 z-50 glass border-b border-zinc-800/40 bg-noise">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-4 px-8 py-3.5">
        <div className="flex items-center gap-4">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-400 to-emerald-400 shadow-lg shadow-indigo-500/20">
            <span className="font-display text-sm font-extrabold text-white tracking-tight">FS</span>
            <div className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#06070a] bg-emerald-400" />
          </div>
          <div>
            <h1 className="font-display text-[17px] font-bold tracking-tight text-white">
              Finance Stack
            </h1>
            <p className="text-[11px] font-medium text-zinc-500 tracking-wide">
              MCP-native paper trading engine
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="flex items-center glass-input rounded-xl overflow-hidden">
            <span className="pl-3.5 text-[11px] font-semibold text-zinc-500 select-none">$</span>
            <input
              type="text"
              inputMode="numeric"
              className="w-24 bg-transparent px-1.5 py-2 font-mono text-sm text-zinc-100 tabular-nums outline-none border-none"
              value={depositAmt}
              onChange={(e) => {
                const v = e.target.value.replace(/[^0-9]/g, '')
                setDepositAmt(v)
              }}
              placeholder="Amount"
            />
            <div className="flex flex-col border-l border-zinc-700/30">
              <button
                type="button"
                onClick={() => nudge(1000)}
                className="px-2 py-0.5 text-zinc-500 transition-colors hover:text-white hover:bg-zinc-700/30 active:bg-zinc-600/30"
              >
                <svg width="10" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 4.5L5 1.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
              <button
                type="button"
                onClick={() => nudge(-1000)}
                className="px-2 py-0.5 text-zinc-500 transition-colors hover:text-white hover:bg-zinc-700/30 active:bg-zinc-600/30"
              >
                <svg width="10" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1.5L5 4.5L9 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
            </div>
          </div>
          <button
            type="button"
            className="btn-success rounded-xl px-5 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={() => deposit.mutate(Number(depositAmt))}
            disabled={deposit.isPending}
          >
            {deposit.isPending ? 'Depositing…' : 'Deposit'}
          </button>
          <button
            type="button"
            className="glass-input rounded-xl px-4 py-2 text-sm font-medium text-zinc-500 transition-colors hover:text-zinc-200 hover:border-zinc-600/50"
            onClick={() => reset.mutate()}
            disabled={reset.isPending}
          >
            Reset
          </button>
        </div>
      </div>
    </header>
  )
}
