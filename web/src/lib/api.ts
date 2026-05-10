import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import type {
  AgentData,
  AgentAction,
  AgentStats,
  AlertNotification,
  AlertRule,
  ApiKeyData,
  AuditEvent,
  BacktestResult,
  BacktestRun,
  CausalChain,
  CausalCounterfactual,
  CausalEvent,
  CausalReplaySummary,
  BrokerStatusData,
  EquityPoint,
  ExecutionPlanData,
  ExecutionQualityData,
  Fill,
  MetricsData,
  Order,
  OrderIntent,
  Portfolio,
  QuoteData,
  ReconciliationResult,
  ResearchRunDetail,
  ResearchRunSummary,
  ReplayState,
  RiskMetrics,
  RiskSnapshot,
  RiskWhatIfResult,
  StrategyInfo,
  StrategySignal,
  SimulationRunResult,
  SimulationScenario,
  SimulationCompareResult,
  SimulationScenarioVersion,
  SweepResult,
  VenueOrder,
  VenueStatus,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

const STALE = 3_000

export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: () => request<Portfolio>('/api/portfolio'),
    staleTime: STALE,
  })
}

export function useOrders(limit = 40) {
  return useQuery({
    queryKey: ['orders'],
    queryFn: () => request<{ orders: Order[] }>(`/api/orders?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useFills(limit = 40) {
  return useQuery({
    queryKey: ['fills'],
    queryFn: () => request<{ fills: Fill[] }>(`/api/fills?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useAudit(limit = 60) {
  return useQuery({
    queryKey: ['audit'],
    queryFn: () => request<{ events: AuditEvent[] }>(`/api/audit?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useEquitySeries(limit = 300) {
  return useQuery({
    queryKey: ['equity'],
    queryFn: () => request<{ points: EquityPoint[] }>(`/api/equity-series?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useQuotes(symbols: string) {
  return useQuery({
    queryKey: ['quotes', symbols],
    queryFn: () => request<{ quotes: QuoteData[] }>(`/api/quotes?symbols=${encodeURIComponent(symbols)}`),
    enabled: symbols.length > 0,
  })
}

export function useRisk() {
  return useQuery({
    queryKey: ['risk'],
    queryFn: () => request<RiskMetrics>('/api/risk'),
    staleTime: 5_000,
  })
}

export function useRiskSnapshot() {
  return useQuery({
    queryKey: ['risk-snapshot'],
    queryFn: () => request<RiskSnapshot>('/api/risk/snapshot'),
    staleTime: 5_000,
  })
}

export function useRiskWhatIf() {
  return useMutation({
    mutationFn: (body: {
      symbol: string
      side: string
      quantity: number
      order_kind?: string
      limit_price?: number | null
      agent_id?: number | null
      tool?: string
    }) => request<RiskWhatIfResult>('/api/risk/what-if', { method: 'POST', body: JSON.stringify(body) }),
  })
}

export function useSimulationScenarios(limit = 100) {
  return useQuery({
    queryKey: ['sim-scenarios'],
    queryFn: () => request<{ scenarios: SimulationScenario[] }>(`/api/sim/scenarios?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useCreateSimulationScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      name: string
      description?: string
      note?: string
      legs: Array<{
        symbol: string
        side: string
        quantity: number
        order_kind?: string
        limit_price?: number | null
      }>
    }) => request('/api/sim/scenarios', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sim-scenarios'] }),
  })
}

export function useDeleteSimulationScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (scenarioId: number) =>
      request(`/api/sim/scenarios/${scenarioId}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sim-scenarios'] }),
  })
}

export function useRunSimulation() {
  return useMutation({
    mutationFn: (body: {
      scenario_id?: number
      legs?: Array<{
        symbol: string
        side: string
        quantity: number
        order_kind?: string
        limit_price?: number | null
      }>
    }) => request<SimulationRunResult>('/api/sim/run', { method: 'POST', body: JSON.stringify(body) }),
  })
}

export function useCompareSimulation() {
  return useMutation({
    mutationFn: (body: { baseline_scenario_id: number; candidate_scenario_id: number }) =>
      request<SimulationCompareResult>('/api/sim/compare', { method: 'POST', body: JSON.stringify(body) }),
  })
}

export function useSimulationScenarioVersions(scenarioId: number | null) {
  return useQuery({
    queryKey: ['sim-scenario-versions', scenarioId],
    queryFn: () =>
      request<{ versions: SimulationScenarioVersion[] }>(`/api/sim/scenarios/${scenarioId}/versions`),
    enabled: scenarioId != null,
    staleTime: STALE,
  })
}

export function usePromoteSimulation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      baseline_scenario_id: number
      candidate_scenario_id: number
      note?: string
    }) => request('/api/sim/promote', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sim-scenarios'] })
      qc.invalidateQueries({ queryKey: ['sim-scenario-versions'] })
    },
  })
}

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => request<{ agents: AgentData[] }>('/api/agents'),
    staleTime: STALE,
  })
}

export function useAgentStats(agentId: number | null) {
  return useQuery({
    queryKey: ['agent-stats', agentId],
    queryFn: () => request<AgentStats>(`/api/agents/${agentId}`),
    enabled: agentId != null,
  })
}

export function useReplay(eventId: number | null) {
  return useQuery({
    queryKey: ['replay', eventId],
    queryFn: () => request<ReplayState>(`/api/replay?event_id=${eventId}`),
    enabled: eventId != null,
  })
}

export function useEventTimeline() {
  return useQuery({
    queryKey: ['event-timeline'],
    queryFn: () =>
      request<{ events: Array<{ id: number; ts: string; action: string }>; max_event_id: number }>(
        '/api/event-timeline?limit=500',
      ),
    staleTime: 5_000,
  })
}

export function useDeposit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (amount: number) =>
      request('/api/deposit', { method: 'POST', body: JSON.stringify({ amount }) }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useResetDemo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => request('/api/reset-demo', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useToggleTrading() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) =>
      request('/api/trading-enabled', { method: 'POST', body: JSON.stringify({ enabled }) }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useCancelOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (orderId: number) =>
      request(`/api/cancel-order/${orderId}`, { method: 'POST', body: '{}' }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function usePlaceOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      client_order_id: string
      symbol: string
      side: string
      quantity: number
      order_kind: string
      limit_price?: number | null
      agent_id?: number | null
    }) => request('/api/place-order', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useRegisterAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      name: string
      budget: number
      allowed_symbols?: string[]
      allowed_mcp_tools?: string[] | null
    }) =>
      request('/api/agents', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useBrokerReconciliation() {
  return useQuery({
    queryKey: ['broker-reconciliation'],
    queryFn: () => request<ReconciliationResult>('/api/broker/reconciliation'),
    staleTime: 5_000,
  })
}

export function usePendingOrderIntents(limit = 100) {
  return useQuery({
    queryKey: ['order-intents-pending'],
    queryFn: () => request<{ intents: OrderIntent[] }>(`/api/order-intents/pending?limit=${limit}`),
    staleTime: 3_000,
  })
}

export function useRecentAgentActions(limit = 50) {
  return useQuery({
    queryKey: ['agent-actions-recent'],
    queryFn: () => request<{ actions: AgentAction[] }>(`/api/agent-actions/recent?limit=${limit}`),
    staleTime: 3_000,
  })
}

export function useCreateAgentOrderIntent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      client_order_id: string
      symbol: string
      side: string
      quantity: number
      order_kind: string
      limit_price?: number | null
      agent_id: number
    }) => request('/api/agent-actions/order-intent', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['order-intents-pending'] })
      qc.invalidateQueries({ queryKey: ['agent-actions-recent'] })
      qc.invalidateQueries({ queryKey: ['audit'] })
    },
  })
}

export function useApproveOrderIntent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (intentId: number) =>
      request(`/api/order-intents/${intentId}/approve`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['order-intents-pending'] })
      qc.invalidateQueries({ queryKey: ['orders'] })
      qc.invalidateQueries({ queryKey: ['fills'] })
      qc.invalidateQueries({ queryKey: ['portfolio'] })
      qc.invalidateQueries({ queryKey: ['agent-actions-recent'] })
      qc.invalidateQueries({ queryKey: ['audit'] })
    },
  })
}

export function useRejectOrderIntent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (intentId: number) =>
      request(`/api/order-intents/${intentId}/reject`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['order-intents-pending'] })
      qc.invalidateQueries({ queryKey: ['agent-actions-recent'] })
      qc.invalidateQueries({ queryKey: ['audit'] })
    },
  })
}

export function useRunBacktest() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      request<BacktestResult>('/api/backtest', { method: 'POST', body: JSON.stringify(body) }),
  })
}

export function useResearchRuns(limit = 20) {
  return useQuery({
    queryKey: ['research-runs'],
    queryFn: () => request<{ runs: ResearchRunSummary[] }>(`/api/research/runs?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useResearchRun(runId: number | null) {
  return useQuery({
    queryKey: ['research-run', runId],
    queryFn: () => request<ResearchRunDetail>(`/api/research/runs/${runId}`),
    enabled: runId != null,
    staleTime: STALE,
  })
}

export function useRunWalkForwardResearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      name?: string
      strategy_name: string
      symbols: string[]
      total_bars: number
      train_bars: number
      test_bars: number
      step_bars: number
      seed: number
      drift: number
      volatility: number
      correlation: number
      strategy_params?: Record<string, unknown>
    }) => request<ResearchRunDetail>('/api/research/walk-forward', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['research-runs'] })
      qc.setQueryData(['research-run', r.id], r)
    },
  })
}

export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: () => request<MetricsData>('/api/metrics'),
    staleTime: 5_000,
    refetchInterval: (q) => (q.state.status === 'success' ? 10_000 : false),
  })
}

export function useCausalEvents(limit = 80) {
  return useQuery({
    queryKey: ['causal-events', limit],
    queryFn: () => request<{ events: CausalEvent[] }>(`/api/causal/events?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useCausalChain(eventId: number | null) {
  return useQuery({
    queryKey: ['causal-chain', eventId],
    queryFn: () => request<CausalChain>(`/api/causal/events/${eventId}/chain`),
    enabled: eventId != null,
    staleTime: STALE,
  })
}

export function useCausalReplay(toEventId: number | null = null) {
  const suffix = toEventId != null ? `?to_event_id=${toEventId}` : ''
  return useQuery({
    queryKey: ['causal-replay', toEventId],
    queryFn: () => request<CausalReplaySummary>(`/api/causal/replay${suffix}`),
    staleTime: STALE,
  })
}

export function useCausalCounterfactual() {
  return useMutation({
    mutationFn: (body: {
      max_order_notional?: number | null
      max_gross_exposure_multiple?: number | null
      require_approval_for_all_agents?: boolean
      limit?: number
    }) => request<CausalCounterfactual>('/api/causal/counterfactual', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  })
}

export function useVenueStatus() {
  return useQuery({
    queryKey: ['venue-status'],
    queryFn: () => request<VenueStatus>('/api/venue/status'),
    staleTime: STALE,
  })
}

export function useVenueOrders(limit = 100) {
  return useQuery({
    queryKey: ['venue-orders'],
    queryFn: () => request<{ orders: VenueOrder[] }>(`/api/venue/orders?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useSubmitVenueOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      client_order_id: string
      symbol: string
      side: string
      quantity: number
      order_type: string
      limit_price?: number | null
      time_in_force?: string
      depth_per_tick?: number
      latency_ticks?: number
    }) => request<VenueOrder>('/api/venue/orders', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['venue-orders'] })
      qc.invalidateQueries({ queryKey: ['venue-status'] })
      qc.invalidateQueries({ queryKey: ['portfolio'] })
      qc.invalidateQueries({ queryKey: ['causal-events'] })
    },
  })
}

export function useTickVenue() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => request('/api/venue/tick', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['venue-orders'] })
      qc.invalidateQueries({ queryKey: ['venue-status'] })
      qc.invalidateQueries({ queryKey: ['portfolio'] })
      qc.invalidateQueries({ queryKey: ['causal-events'] })
    },
  })
}

export function useApiKeys() {
  return useQuery({
    queryKey: ['api-keys'],
    queryFn: () => request<{ keys: ApiKeyData[] }>('/api/keys'),
    staleTime: STALE,
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; role: string }) =>
      request<ApiKeyData>('/api/keys', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

export function useRevokeApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: number) =>
      request(`/api/keys/${keyId}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

export function useSweepFills() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      request<{ sweeps: SweepResult[] }>('/api/sweep-fills', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useBacktestHistory(limit = 20) {
  return useQuery({
    queryKey: ['backtest-history'],
    queryFn: () => request<{ runs: BacktestRun[] }>(`/api/backtest-history?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useAlerts() {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: () => request<{ rules: AlertRule[] }>('/api/alerts'),
    staleTime: STALE,
  })
}

export function useAlertNotifications(limit = 50) {
  return useQuery({
    queryKey: ['alert-notifications'],
    queryFn: () =>
      request<{ notifications: AlertNotification[] }>(`/api/alert-notifications?limit=${limit}`),
    staleTime: STALE,
  })
}

export function useCreateAlert() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; alert_type: string; threshold: number; symbol: string | null }) =>
      request('/api/alerts', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}

export function useDeleteAlert() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ruleId: number) =>
      request(`/api/alerts/${ruleId}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}

export function useEvaluateAlerts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      request('/api/alerts/evaluate', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alert-notifications'] }),
  })
}

// ── strategies ───────────────────────────────────────────────

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: () => request<{ strategies: StrategyInfo[] }>('/api/strategies'),
    staleTime: STALE,
  })
}

export function useToggleStrategy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      request(`/api/strategies/${name}/toggle`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })
}

export function useConfigureStrategy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, params }: { name: string; params: Record<string, unknown> }) =>
      request(`/api/strategies/${name}/configure`, {
        method: 'POST',
        body: JSON.stringify({ params }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })
}

export function useStrategySignals(name?: string, limit = 50) {
  const path = name ? `/api/strategies/${name}/signals?limit=${limit}` : `/api/strategies/signals?limit=${limit}`
  return useQuery({
    queryKey: ['strategy-signals', name],
    queryFn: () => request<{ signals: StrategySignal[] }>(path),
    staleTime: STALE,
  })
}

export function useRunStrategiesOnce() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      request<{ signals: StrategySignal[] }>('/api/strategies/run-once', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-signals'] })
      qc.invalidateQueries({ queryKey: ['strategies'] })
    },
  })
}

export function useStartStrategyEngine() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => request('/api/strategies/start-engine', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['broker-status'] }),
  })
}

export function useStopStrategyEngine() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => request('/api/strategies/stop-engine', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['broker-status'] }),
  })
}

export function useBrokerStatus() {
  return useQuery({
    queryKey: ['broker-status'],
    queryFn: () => request<BrokerStatusData>('/api/broker-status'),
    staleTime: 5_000,
  })
}

export function useCreateExecutionPlan() {
  return useMutation({
    mutationFn: (body: {
      symbol: string
      side: string
      quantity: number
      algorithm: string
      num_slices?: number
      interval_seconds?: number
    }) =>
      request<ExecutionPlanData>('/api/execution-plan', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  })
}

export function useExecutionQuality(limitOrders = 500) {
  return useQuery({
    queryKey: ['execution-quality', limitOrders],
    queryFn: () =>
      request<ExecutionQualityData>(`/api/execution/quality?limit_orders=${limitOrders}`),
    staleTime: 5_000,
  })
}

const LIVE_KEYS = [
  'portfolio', 'orders', 'fills', 'equity', 'audit', 'risk',
  'agents', 'event-timeline', 'alert-notifications', 'backtest-history',
  'strategies', 'strategy-signals', 'broker-status',
  'broker-reconciliation', 'order-intents-pending', 'risk-snapshot',
  'sim-scenarios',
  'execution-quality',
]

export function useWebSocket() {
  const qc = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${window.location.host}/api/ws`
    let ws: WebSocket
    let closed = false
    let timer: ReturnType<typeof setTimeout> | null = null

    let attempt = 0
    function connect() {
      if (closed) return
      ws = new WebSocket(url)
      wsRef.current = ws
      ws.onopen = () => {
        attempt = 0
      }
      ws.onmessage = () => {
        for (const key of LIVE_KEYS) {
          qc.invalidateQueries({ queryKey: [key] })
        }
      }
      ws.onclose = () => {
        if (closed) return
        attempt += 1
        const delay = Math.min(3_000 * 2 ** (attempt - 1), 30_000)
        timer = setTimeout(connect, delay)
      }
      ws.onerror = () => {
        ws.close()
      }
    }

    timer = setTimeout(connect, 0)
    return () => {
      closed = true
      if (timer) clearTimeout(timer)
      ws?.close()
    }
  }, [qc])
}

export const fmt = (n: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(n)

export const fmtPnl = (n: number) => {
  const s = fmt(Math.abs(n))
  if (n > 0.005) return `+${s}`
  if (n < -0.005) return `-${s}`
  return s
}

export const pct = (n: number) => `${(n * 100).toFixed(2)}%`
