import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

type LandingPageProps = {
  onEnterApp: () => void
  onOpenDocs: () => void
}

const DEPTH = [
  ['Policy layer', 'Active state, budget, allowed symbols, maximum order size, and MCP tool scope.'],
  ['Decision records', 'ALLOW, REJECT, RESIZE, and REQUIRE_APPROVAL outcomes with structured reasons.'],
  ['Research lab', 'Walk-forward validation, benchmarks, turnover, exposure, and signal diagnostics.'],
  ['Execution venue', 'Local market simulator with fills mirrored into the ledger.'],
  ['Forensics', 'Audit integrity, event replay, decision paths, and counterfactual policy checks.'],
  ['MCP-native', 'Designed for agents to propose actions through controlled tool boundaries.'],
]

const STAGES = [
  {
    step: '01',
    title: 'Agent proposal',
    headline: 'Every action starts with a constrained identity.',
    body: 'An agent does not get a vague permission to trade. The request carries its budget, symbol scope, maximum order size, and MCP tool permissions into the control plane.',
    bullets: ['Agent: alpha-1', 'Request: BUY 25 AAPL', 'Scope: AAPL, MSFT, SPY', 'Tool: place_order'],
  },
  {
    step: '02',
    title: 'Risk decision',
    headline: 'The system explains the trade before it can execute.',
    body: 'The decision engine checks policy, cash, position impact, gross exposure, concentration, and VaR/CVaR budget. The result is not a boolean; it is an explained decision.',
    bullets: ['Decision: REQUIRE_APPROVAL', 'Exposure: 0.42x', 'Concentration: review', 'VaR/CVaR: inside limits'],
  },
  {
    step: '03',
    title: 'Human review',
    headline: 'High-risk actions pause for approval.',
    body: 'When policy requires review, the trade becomes an approval item. Approving it runs the final pre-trade checks again, so stale approvals cannot bypass current risk.',
    bullets: ['Queue: pending', 'Action: approve or reject', 'Final check: required', 'Audit: decision recorded'],
  },
  {
    step: '04',
    title: 'Execution simulation',
    headline: 'Orders face a local market, not a fake instant fill.',
    body: 'The simulated venue models spread, depth, impact, latency, partial fills, cancellation, and order status. It gives agents realistic execution friction without touching live capital.',
    bullets: ['Status: accepted', 'Depth: constrained', 'Fill: partial or complete', 'Ledger: mirrored'],
  },
  {
    step: '05',
    title: 'Audit replay',
    headline: 'The evidence remains inspectable after the action.',
    body: 'The event log records the proposal, risk explanation, human decision, execution result, and portfolio change. A reviewer can replay the path and test counterfactual policies later.',
    bullets: ['Proposal recorded', 'Risk attached', 'Decision linked', 'Portfolio updated'],
  },
]

export default function LandingPage({ onEnterApp, onOpenDocs }: LandingPageProps) {
  const flowRef = useRef<HTMLElement | null>(null)

  return (
    <div className="min-h-screen overflow-hidden bg-[#050609] text-zinc-100">
      <header className="fixed left-0 right-0 top-0 z-30 border-b border-white/[0.06] bg-[#050609]/65 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-4 md:px-10">
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06]">
              <span className="font-display text-xs font-extrabold text-white">AC</span>
              <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#050609] bg-emerald-400" />
            </div>
            <div>
              <p className="font-display text-sm font-bold tracking-tight text-white">Agent Control Plane</p>
              <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-600">Local trading control plane</p>
            </div>
          </div>
          <nav className="hidden items-center gap-7 text-xs font-semibold text-zinc-500 md:flex">
            <button type="button" className="transition-colors hover:text-zinc-200" onClick={() => flowRef.current?.scrollIntoView({ behavior: 'smooth' })}>
              Flow
            </button>
            <a className="transition-colors hover:text-zinc-200" href="#depth">Depth</a>
            <button type="button" className="transition-colors hover:text-zinc-200" onClick={onOpenDocs}>Docs</button>
            <button type="button" className="rounded-full bg-emerald-400 px-4 py-2 font-bold text-zinc-950 transition-transform hover:-translate-y-0.5" onClick={onEnterApp}>
              Open app
            </button>
          </nav>
          <button type="button" className="rounded-full bg-emerald-400 px-4 py-2 text-xs font-bold text-zinc-950 md:hidden" onClick={onEnterApp}>
            Open
          </button>
        </div>
      </header>

      <main>
        <section className="relative min-h-[92vh] border-b border-white/[0.06]">
          <AgentGraphScene />
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,#050609_0%,rgba(5,6,9,0.9)_28%,rgba(5,6,9,0.35)_70%,rgba(5,6,9,0.72)_100%)]" />
          <div className="relative z-10 mx-auto flex min-h-[92vh] max-w-[1440px] items-center px-6 pb-16 pt-28 md:px-10">
            <div className="max-w-4xl">
              <p className="mb-5 inline-flex rounded-full border border-emerald-400/20 bg-emerald-400/5 px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                MCP-native financial control plane
              </p>
              <h1 className="font-display text-5xl font-black leading-[0.98] tracking-tight text-white md:text-7xl lg:text-8xl">
                Govern AI agents before they move money.
              </h1>
              <p className="mt-7 max-w-2xl text-base leading-7 text-zinc-400 md:text-lg">
                A local control plane for testing agent trading actions under policy, risk checks, human approval, simulated execution, and replayable audit.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <button type="button" className="rounded-full bg-white px-5 py-3 text-sm font-bold text-zinc-950 transition-transform hover:-translate-y-0.5" onClick={onEnterApp}>
                  Open Control Plane
                </button>
                <button type="button" className="rounded-full border border-white/12 bg-white/[0.04] px-5 py-3 text-sm font-bold text-zinc-200 transition-colors hover:border-emerald-400/30 hover:text-white" onClick={() => flowRef.current?.scrollIntoView({ behavior: 'smooth' })}>
                  View Demo Flow
                </button>
              </div>
              <div className="mt-12 grid max-w-3xl gap-3 sm:grid-cols-4">
                <Proof label="Policy" value="Enforced" />
                <Proof label="Risk" value="Explained" />
                <Proof label="Approval" value="Human review" />
                <Proof label="Audit" value="Replayable" />
              </div>
            </div>
          </div>
          <div className="absolute bottom-5 left-1/2 z-10 hidden -translate-x-1/2 items-center gap-2 font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-600 md:flex">
            <span className="h-px w-10 bg-white/10" />
            product flow
            <span className="h-px w-10 bg-white/10" />
          </div>
        </section>

        <section ref={flowRef} className="border-y border-white/[0.06] bg-white/[0.018]">
          <div className="mx-auto max-w-[1440px] px-6 py-20 md:px-10">
            <div className="mb-16 max-w-4xl">
              <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-indigo-300">Controlled workflow</p>
              <h2 className="mt-3 font-display text-4xl font-bold tracking-tight text-white md:text-6xl">
                Scroll through the path from agent proposal to audit evidence.
              </h2>
              <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-500">
                Each stage adds a constraint, explanation, or record. The product is not a charting dashboard; it is an operating layer for financial actions.
              </p>
            </div>
            <ScrollWorkflow />
          </div>
        </section>

        <section id="depth" className="border-y border-white/[0.06] bg-white/[0.025]">
          <div className="mx-auto grid max-w-[1440px] gap-12 px-6 py-20 md:px-10 xl:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-emerald-300">Technical depth</p>
              <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white md:text-5xl">
                Built for controlled autonomy, not trading hype.
              </h2>
              <p className="mt-5 max-w-lg text-sm leading-7 text-zinc-500">
                Agents can propose actions. The system evaluates each request, explains the decision, applies human review when needed, executes locally, and records the audit trail.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {DEPTH.map(([title, body]) => (
                <article key={title} className="rounded-2xl border border-white/[0.08] bg-[#080a0f] p-5">
                  <h3 className="font-display text-base font-bold text-white">{title}</h3>
                  <p className="mt-3 text-sm leading-6 text-zinc-500">{body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-[1440px] px-6 py-16 md:px-10">
          <div className="grid gap-4 rounded-3xl border border-white/[0.08] bg-[#080a0f] p-5 md:grid-cols-4">
            <FooterMetric label="Default mode" value="Local simulation" />
            <FooterMetric label="Human review" value="Approval queue" />
            <FooterMetric label="Evidence" value="Audit replay" />
            <FooterMetric label="Deployment" value="Single container" />
          </div>
        </section>

        <section id="documentation" className="mx-auto grid max-w-[1440px] gap-10 px-6 py-20 md:px-10 xl:grid-cols-[0.85fr_1.15fr]">
          <div>
            <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-indigo-300">Scientific documentation</p>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white md:text-5xl">
              Explain the method, not just the interface.
            </h2>
            <p className="mt-5 max-w-lg text-sm leading-7 text-zinc-500">
              Because the product is technical, the documentation should read like a short methodology paper: assumptions, controls, risk model, execution model, audit model, and limits.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <DocCard title="Governance model" body="How agent identity, allowed tools, budgets, and symbol scopes constrain every proposed action." />
            <DocCard title="Risk methodology" body="How the system estimates notional exposure, concentration, cash checks, VaR/CVaR status, and approval thresholds." />
            <DocCard title="Execution model" body="How the local venue simulates spread, impact, depth, latency, partial fills, and cancellation." />
            <DocCard title="Audit and replay" body="How decisions, approvals, fills, and portfolio changes become reviewable evidence." />
          </div>
          <div className="xl:col-start-2">
            <button type="button" className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-5 py-3 text-sm font-bold text-emerald-300 transition-colors hover:bg-emerald-400/15" onClick={onOpenDocs}>
              Read methodology
            </button>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-4 px-6 py-8 text-xs text-zinc-600 md:px-10">
          <p>© 2026 Duy Huynh. All rights reserved.</p>
          <div className="flex gap-5">
            <button type="button" className="transition-colors hover:text-zinc-300" onClick={onOpenDocs}>Scientific documentation</button>
            <a className="transition-colors hover:text-zinc-300" href="mailto:privacy@duyhuynh.dev">Privacy</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

function ScrollWorkflow() {
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const [activeStage, setActiveStage] = useState(0)

  useEffect(() => {
    const update = () => {
      const el = scrollerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const scrollable = Math.max(rect.height - window.innerHeight, 1)
      const progress = Math.min(Math.max(-rect.top / scrollable, 0), 0.999)
      setActiveStage(Math.floor(progress * STAGES.length))
    }

    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [])

  return (
    <div ref={scrollerRef} className="relative min-h-[520vh]">
      <div className="sticky top-20 grid min-h-[calc(100vh-5rem)] items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <div className="mb-8 max-w-2xl">
            <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-emerald-300">
              Stage {STAGES[activeStage].step}
            </p>
            <h3 className="mt-3 font-display text-3xl font-bold leading-tight tracking-tight text-white md:text-5xl">
              {STAGES[activeStage].headline}
            </h3>
          </div>

          <div className="overflow-hidden rounded-3xl border border-white/[0.08] bg-[#080a0f]">
            {STAGES.map((stage, index) => {
              const active = index === activeStage
              return (
                <button
                  key={stage.title}
                  type="button"
                  className={`block w-full border-b border-white/[0.08] px-5 py-5 text-left transition-all duration-500 last:border-b-0 ${
                    active ? 'bg-white/[0.035]' : 'bg-transparent hover:bg-white/[0.02]'
                  }`}
                  onClick={() => setActiveStage(index)}
                >
                  <div className="flex items-center gap-5">
                    <span className={`font-mono text-xs ${active ? 'text-emerald-300' : 'text-zinc-600'}`}>
                      {stage.step}
                    </span>
                    <span className={`font-display text-sm font-bold uppercase tracking-[0.12em] ${active ? 'text-white' : 'text-zinc-500'}`}>
                      {stage.title}
                    </span>
                  </div>
                  <div className={`grid transition-all duration-500 ${active ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
                    <div className="overflow-hidden">
                      <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-400">{stage.body}</p>
                      <div className="mt-5 grid gap-2 sm:grid-cols-2">
                        {stage.bullets.map((item) => (
                          <div key={item} className="rounded-2xl border border-white/[0.06] bg-black/20 px-3 py-3">
                            <p className="font-mono text-xs text-zinc-300">{item}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div key={activeStage} className="animate-fade-in-up transition-all duration-500">
          <StageVisual index={activeStage} />
        </div>
      </div>
    </div>
  )
}

function StageVisual({ index }: { index: number }) {
  const panels = [
    <div className="space-y-3" key="proposal">
      <VisualHeader label="Proposal envelope" status="scoped" />
      <VisualRow label="Agent" value="alpha-1" tone="indigo" />
      <VisualRow label="Tool" value="place_order" tone="emerald" />
      <VisualRow label="Budget" value="$50,000" tone="zinc" />
      <VisualRow label="Allowed symbols" value="AAPL · MSFT · SPY" tone="zinc" />
      <FlowLine labels={['request', 'identity', 'policy']} />
    </div>,
    <div className="space-y-3" key="risk">
      <VisualHeader label="Decision engine" status="require approval" tone="amber" />
      <DecisionCheck label="Agent permissions" tone="emerald" value="passed" />
      <DecisionCheck label="Cash and position" tone="emerald" value="passed" />
      <DecisionCheck label="Gross exposure" tone="emerald" value="0.42x" />
      <DecisionCheck label="Concentration" tone="amber" value="review" />
      <DecisionCheck label="VaR / CVaR budget" tone="emerald" value="inside limits" />
      <DecisionCheck label="Approval policy" tone="amber" value="required" />
    </div>,
    <div className="space-y-4" key="approval">
      <VisualHeader label="Approval queue" status="pending" tone="amber" />
      <div className="rounded-2xl border border-amber-300/20 bg-amber-300/[0.04] p-4">
        <p className="font-display text-xl font-bold text-white">BUY 25 AAPL</p>
        <p className="mt-2 text-xs leading-5 text-zinc-500">Reason: concentration review required before execution.</p>
        <div className="mt-5 flex gap-2">
          <span className="rounded-full bg-emerald-400 px-4 py-2 text-xs font-bold text-zinc-950">Approve</span>
          <span className="rounded-full border border-rose-400/30 px-4 py-2 text-xs font-bold text-rose-300">Reject</span>
        </div>
      </div>
      <FlowLine labels={['review', 'recheck', 'record']} />
    </div>,
    <div className="space-y-3" key="venue">
      <VisualHeader label="Execution venue" status="simulated" />
      <VenueStep label="Accepted" active />
      <VenueStep label="Open" active />
      <VenueStep label="Partial fill" active />
      <VenueStep label="Filled" />
      <div className="grid grid-cols-3 gap-2 pt-2">
        <VisualStat label="Spread" value="2.4 bps" />
        <VisualStat label="Impact" value="4.1 bps" />
        <VisualStat label="Latency" value="2 ticks" />
      </div>
    </div>,
    <div className="space-y-3" key="audit">
      <VisualHeader label="Audit replay" status="valid" />
      {['proposal recorded', 'risk explanation attached', 'approval decision linked', 'venue fill mirrored', 'portfolio state updated'].map((item) => (
        <div key={item} className="flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.025] px-3 py-3 text-xs text-zinc-400">
          <span className="h-px w-8 bg-emerald-300/50" />
          {item}
        </div>
      ))}
    </div>
  ]

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-black/20 p-5">
      <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px)] [background-size:42px_42px]" />
      <div className="relative">{panels[index]}</div>
    </div>
  )
}

function VisualHeader({ label, status, tone = 'emerald' }: { label: string; status: string; tone?: 'emerald' | 'amber' }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-600">{label}</p>
      <span className={`rounded-full px-3 py-1 font-mono text-[10px] font-bold ${tone === 'amber' ? 'bg-amber-400/10 text-amber-300' : 'bg-emerald-400/10 text-emerald-300'}`}>
        {status}
      </span>
    </div>
  )
}

function VisualRow({ label, value, tone }: { label: string; value: string; tone: 'emerald' | 'indigo' | 'zinc' }) {
  const color = tone === 'emerald' ? 'text-emerald-300' : tone === 'indigo' ? 'text-indigo-300' : 'text-zinc-300'
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.025] px-4 py-3">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={`font-mono text-xs font-semibold ${color}`}>{value}</span>
    </div>
  )
}

function FlowLine({ labels }: { labels: string[] }) {
  return (
    <div className="grid grid-cols-3 gap-2 pt-4">
      {labels.map((label) => (
        <div key={label} className="rounded-full border border-emerald-300/20 bg-emerald-300/[0.04] px-3 py-2 text-center font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-300">
          {label}
        </div>
      ))}
    </div>
  )
}

function VenueStep({ label, active }: { label: string; active?: boolean }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.025] px-4 py-3">
      <span className={`h-2.5 w-2.5 rounded-full ${active ? 'bg-emerald-300' : 'bg-zinc-700'}`} />
      <span className="text-sm font-semibold text-zinc-300">{label}</span>
    </div>
  )
}

function VisualStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.025] px-3 py-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-600">{label}</p>
      <p className="mt-1 font-mono text-xs text-zinc-200">{value}</p>
    </div>
  )
}

function DocCard({ title, body }: { title: string; body: string }) {
  return (
    <article className="rounded-2xl border border-white/[0.08] bg-[#080a0f] p-5">
      <h3 className="font-display text-base font-bold text-white">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-zinc-500">{body}</p>
    </article>
  )
}

function DecisionCheck({ label, value, tone }: { label: string; value: string; tone: 'emerald' | 'amber' }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] px-3 py-2">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={`font-mono text-[11px] font-semibold ${tone === 'emerald' ? 'text-emerald-300' : 'text-amber-300'}`}>
        {value}
      </span>
    </div>
  )
}

function FooterMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-l border-white/10 pl-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-600">{label}</p>
      <p className="mt-2 font-display text-lg font-bold text-white">{value}</p>
    </div>
  )
}

function AgentGraphScene() {
  const mountRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(42, mount.clientWidth / mount.clientHeight, 0.1, 100)
    camera.position.set(0, 1.8, 9)

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      return setupCanvasFallback(mount)
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    group.position.set(2.4, 0, 0)
    scene.add(group)

    const agentMat = new THREE.MeshStandardMaterial({ color: '#818cf8', roughness: 0.32, metalness: 0.25 })
    const riskMat = new THREE.MeshStandardMaterial({ color: '#34d399', roughness: 0.28, metalness: 0.2 })
    const auditMat = new THREE.MeshStandardMaterial({ color: '#fbbf24', roughness: 0.42, metalness: 0.08 })
    const mutedMat = new THREE.MeshStandardMaterial({ color: '#71717a', roughness: 0.55, metalness: 0.1 })
    const lineMat = new THREE.LineBasicMaterial({ color: '#3f465a', transparent: true, opacity: 0.75 })
    const pulseMat = new THREE.MeshBasicMaterial({ color: '#34d399', transparent: true, opacity: 0.9 })

    const sphere = new THREE.SphereGeometry(0.18, 32, 16)
    const smallSphere = new THREE.SphereGeometry(0.09, 20, 10)
    const nodes = [
      new THREE.Vector3(-3.2, 1.35, 0),
      new THREE.Vector3(-3.2, -1.15, 0.2),
      new THREE.Vector3(-1.05, 0.15, 0),
      new THREE.Vector3(1.15, 0.15, 0),
      new THREE.Vector3(3.05, 1.05, 0.15),
      new THREE.Vector3(3.05, -1.05, -0.1),
    ]

    nodes.forEach((pos, index) => {
      const mesh = new THREE.Mesh(sphere, index < 2 ? agentMat : index < 4 ? riskMat : index === 4 ? mutedMat : auditMat)
      mesh.position.copy(pos)
      group.add(mesh)
    })

    const segments = [
      [nodes[0], nodes[2]],
      [nodes[1], nodes[2]],
      [nodes[2], nodes[3]],
      [nodes[3], nodes[4]],
      [nodes[3], nodes[5]],
    ]

    segments.forEach(([a, b]) => {
      const geometry = new THREE.BufferGeometry().setFromPoints([a, b])
      group.add(new THREE.Line(geometry, lineMat))
    })

    const gate = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 2.7, 1.6),
      new THREE.MeshStandardMaterial({ color: '#172018', roughness: 0.18, metalness: 0.1, transparent: true, opacity: 0.72 }),
    )
    gate.position.set(0.05, 0.15, 0)
    group.add(gate)

    const torus = new THREE.Mesh(new THREE.TorusGeometry(1.05, 0.012, 12, 96), new THREE.MeshBasicMaterial({ color: '#818cf8', transparent: true, opacity: 0.32 }))
    torus.position.copy(nodes[2])
    group.add(torus)

    const packets = segments.map(([a, b], index) => {
      const packet = new THREE.Mesh(smallSphere, pulseMat.clone())
      packet.position.copy(a)
      group.add(packet)
      return { packet, a, b, offset: index / segments.length }
    })

    const ambient = new THREE.AmbientLight('#ffffff', 0.78)
    const key = new THREE.PointLight('#818cf8', 2.6, 14)
    key.position.set(-3, 4, 5)
    const fill = new THREE.PointLight('#34d399', 2.1, 12)
    fill.position.set(3, -1, 4)
    scene.add(ambient, key, fill)

    let frame = 0
    let animationId = 0
    const clock = new THREE.Clock()

    const resize = () => {
      const width = mount.clientWidth
      const height = mount.clientHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }

    const animate = () => {
      animationId = window.requestAnimationFrame(animate)
      const t = clock.getElapsedTime()
      group.rotation.y = Math.sin(t * 0.22) * 0.12
      group.rotation.x = Math.sin(t * 0.16) * 0.04
      torus.rotation.z = t * 0.32
      torus.rotation.y = t * 0.18
      gate.scale.y = 1 + Math.sin(t * 1.5) * 0.03
      packets.forEach(({ packet, a, b, offset }) => {
        const k = (t * 0.22 + offset) % 1
        packet.position.lerpVectors(a, b, smooth(k))
        packet.scale.setScalar(0.8 + Math.sin((k + frame * 0.01) * Math.PI) * 0.45)
      })
      renderer.render(scene, camera)
      frame += 1
    }

    window.addEventListener('resize', resize)
    resize()
    animate()

    return () => {
      window.removeEventListener('resize', resize)
      window.cancelAnimationFrame(animationId)
      mount.removeChild(renderer.domElement)
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.Line) {
          obj.geometry.dispose()
          if (Array.isArray(obj.material)) {
            obj.material.forEach((material) => material.dispose())
          } else {
            obj.material.dispose()
          }
        }
      })
      renderer.dispose()
    }
  }, [])

  return <div ref={mountRef} className="absolute inset-0" aria-hidden="true" />
}

function smooth(x: number) {
  return x * x * (3 - 2 * x)
}

function setupCanvasFallback(mount: HTMLDivElement) {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return undefined

  mount.appendChild(canvas)
  let animationId = 0
  let time = 0

  const resize = () => {
    const ratio = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.max(1, Math.floor(mount.clientWidth * ratio))
    canvas.height = Math.max(1, Math.floor(mount.clientHeight * ratio))
    canvas.style.width = `${mount.clientWidth}px`
    canvas.style.height = `${mount.clientHeight}px`
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  }

  const draw = () => {
    animationId = window.requestAnimationFrame(draw)
    const width = mount.clientWidth
    const height = mount.clientHeight
    time += 0.012
    ctx.clearRect(0, 0, width, height)

    const cx = width * 0.67
    const cy = height * 0.52
    const scale = Math.min(width, height) / 640
    const nodes = [
      [cx - 230 * scale, cy - 100 * scale, '#818cf8'],
      [cx - 230 * scale, cy + 105 * scale, '#818cf8'],
      [cx - 60 * scale, cy, '#34d399'],
      [cx + 105 * scale, cy, '#34d399'],
      [cx + 255 * scale, cy - 82 * scale, '#71717a'],
      [cx + 255 * scale, cy + 86 * scale, '#fbbf24'],
    ] as const
    const links = [[0, 2], [1, 2], [2, 3], [3, 4], [3, 5]]

    ctx.lineWidth = 1
    links.forEach(([from, to], index) => {
      const a = nodes[from]
      const b = nodes[to]
      ctx.strokeStyle = 'rgba(99, 110, 140, 0.45)'
      ctx.beginPath()
      ctx.moveTo(a[0], a[1])
      ctx.lineTo(b[0], b[1])
      ctx.stroke()

      const k = smooth((time * 0.22 + index / links.length) % 1)
      const px = a[0] + (b[0] - a[0]) * k
      const py = a[1] + (b[1] - a[1]) * k
      ctx.fillStyle = 'rgba(52, 211, 153, 0.9)'
      ctx.beginPath()
      ctx.arc(px, py, 4 + Math.sin(k * Math.PI) * 3, 0, Math.PI * 2)
      ctx.fill()
    })

    ctx.strokeStyle = 'rgba(52, 211, 153, 0.22)'
    ctx.lineWidth = 2
    ctx.strokeRect(cx - 10 * scale, cy - 145 * scale, 16 * scale, 290 * scale)

    nodes.forEach(([x, y, color], index) => {
      ctx.fillStyle = color
      ctx.globalAlpha = 0.9
      ctx.beginPath()
      ctx.arc(x, y + Math.sin(time * 2 + index) * 3, 11 * scale, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.globalAlpha = 1
  }

  window.addEventListener('resize', resize)
  resize()
  draw()

  return () => {
    window.removeEventListener('resize', resize)
    window.cancelAnimationFrame(animationId)
    mount.removeChild(canvas)
  }
}

function Proof({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-l border-white/10 pl-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-600">{label}</p>
      <p className="mt-1 text-sm font-semibold text-zinc-200">{value}</p>
    </div>
  )
}
