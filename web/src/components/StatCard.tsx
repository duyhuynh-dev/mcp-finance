export default function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: 'emerald' | 'indigo' | 'rose'
}) {
  const colors = {
    emerald: {
      bar: 'from-emerald-400 to-emerald-400/0',
      glow: 'group-hover:shadow-emerald-500/5',
      dot: 'bg-emerald-400',
    },
    indigo: {
      bar: 'from-indigo-400 to-indigo-400/0',
      glow: 'group-hover:shadow-indigo-500/5',
      dot: 'bg-indigo-400',
    },
    rose: {
      bar: 'from-rose-400 to-rose-400/0',
      glow: 'group-hover:shadow-rose-500/5',
      dot: 'bg-rose-400',
    },
  }

  const c = accent ? colors[accent] : {
    bar: 'from-zinc-500/50 to-zinc-500/0',
    glow: '',
    dot: 'bg-zinc-500',
  }

  return (
    <div className={`glass group relative overflow-hidden rounded-2xl p-5 transition-all duration-300 hover:border-zinc-600/40 ${c.glow} hover:shadow-xl`}>
      <div className={`absolute left-0 top-0 h-full w-[2px] bg-gradient-to-b ${c.bar}`} />
      <div className="flex items-center gap-2 mb-2.5">
        <div className={`h-1.5 w-1.5 rounded-full ${c.dot} opacity-60`} />
        <p className="font-display text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">
          {label}
        </p>
      </div>
      <p className="text-[22px] font-bold tracking-tight text-white font-display tabular-nums">
        {value}
      </p>
      {sub && (
        <p className="mt-1.5 text-[11px] font-medium text-zinc-500">{sub}</p>
      )}
    </div>
  )
}
