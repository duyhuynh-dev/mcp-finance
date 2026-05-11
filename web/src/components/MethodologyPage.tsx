type MethodologyPageProps = {
  onBack: () => void
  onEnterApp: () => void
}

const SECTIONS = [
  {
    title: '1. System thesis',
    body: 'The system is designed to test financial actions proposed by AI agents before those actions reach execution. It does not claim to predict markets or generate profitable trades. Its purpose is controlled agency: policy constraints, explainable risk decisions, human review, simulated execution, and audit replay.',
  },
  {
    title: '2. Agent governance',
    body: 'Each agent is treated as a constrained requester. The control layer checks active state, budget, allowed symbols, maximum order size, and permitted MCP tools before accepting a trade proposal or order attempt.',
  },
  {
    title: '3. Risk decision model',
    body: 'For each proposed order, the system estimates mark price, fill price, notional value, projected position, gross exposure, concentration, cash and position feasibility, and risk-budget utilization. The output is ALLOW, REJECT, RESIZE, or REQUIRE_APPROVAL.',
  },
  {
    title: '4. Human review',
    body: 'When a trade requires approval, it becomes a pending review item. Approval does not blindly execute the original request; the system runs the final checks again at approval time to account for changed state.',
  },
  {
    title: '5. Execution simulation',
    body: 'The local venue simulates market mechanics such as spread, depth, market impact, latency, partial fills, cancellation, expiry, and lifecycle status. This gives agents realistic friction without touching live capital.',
  },
  {
    title: '6. Audit and replay',
    body: 'The event log records proposals, decisions, approvals, rejections, fills, portfolio changes, research runs, and integrity state. Reviewers can inspect a decision path and compare how historical actions would change under alternate policies.',
  },
  {
    title: '7. Known limits',
    body: 'This is a local-first control-plane demo. SQLite, mock quotes, and simulated execution are intentional for this phase. Production deployment would require stronger authentication, tenancy, secrets management, broker controls, monitoring, and formal model validation.',
  },
]

export default function MethodologyPage({ onBack, onEnterApp }: MethodologyPageProps) {
  return (
    <div className="min-h-screen bg-[#050609] text-zinc-100">
      <header className="border-b border-white/[0.06]">
        <div className="mx-auto flex max-w-[1100px] items-center justify-between px-6 py-5">
          <button type="button" className="text-xs font-semibold text-zinc-500 transition-colors hover:text-zinc-200" onClick={onBack}>
            Back to landing
          </button>
          <button type="button" className="rounded-full bg-emerald-400 px-4 py-2 text-xs font-bold text-zinc-950" onClick={onEnterApp}>
            Open app
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-6 py-20">
        <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-emerald-300">
          Scientific documentation
        </p>
        <h1 className="mt-4 max-w-4xl font-display text-4xl font-black leading-tight tracking-tight text-white md:text-6xl">
          Methodology for controlled AI-agent financial action.
        </h1>
        <p className="mt-6 max-w-3xl text-base leading-8 text-zinc-500">
          This document explains what the app is measuring, what it deliberately avoids claiming, and how a user should interpret each subsystem.
        </p>

        <div className="mt-14 space-y-4">
          {SECTIONS.map((section) => (
            <section key={section.title} className="rounded-2xl border border-white/[0.08] bg-[#080a0f] p-6">
              <h2 className="font-display text-xl font-bold text-white">{section.title}</h2>
              <p className="mt-3 text-sm leading-7 text-zinc-500">{section.body}</p>
            </section>
          ))}
        </div>
      </main>

      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center justify-between gap-4 px-6 py-8 text-xs text-zinc-600">
          <p>© 2026 Duy Huynh. All rights reserved.</p>
          <a className="transition-colors hover:text-zinc-300" href="mailto:privacy@duyhuynh.dev">Privacy</a>
        </div>
      </footer>
    </div>
  )
}
