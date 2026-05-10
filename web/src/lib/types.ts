export interface PositionData {
  quantity: number
  avg_cost: number
  mark_price: number
  market_value: number
  unrealized_pnl: number
}

export interface PolicyRules {
  version: string
  max_shares_per_symbol: number
  max_order_notional: number
  fee_bps: number
  slippage_bps: number
  slippage_impact_bps_per_million?: number
  max_gross_exposure_multiple?: number
  max_daily_order_count: number
  max_portfolio_concentration_pct: number
  max_portfolio_var_95_pct_of_equity?: number
  max_portfolio_cvar_95_pct_of_equity?: number
}

export interface Portfolio {
  cash: number
  equity: number
  trading_enabled: boolean
  total_realized_pnl: number
  total_unrealized_pnl: number
  positions: Record<string, PositionData>
  rules: PolicyRules
}

export interface Order {
  id: number
  client_order_id: string
  symbol: string
  side: string
  quantity: number
  status: string
  rejection_reason: string | null
  order_kind: string
  limit_price: number | null
  created_at: string
}

export interface Fill {
  id: number
  order_id: number
  symbol: string
  side: string
  quantity: number
  price: number
  fee: number
  realized_pnl: number
  filled_at: string
}

export interface AuditEvent {
  id: number
  ts: string
  actor: string
  action: string
  payload_json: string
  result_json: string | null
}

export interface EquityPoint {
  ts: string
  equity: number
}

export interface QuoteData {
  symbol: string
  price: number | null
  as_of?: string
  error?: string
}

export interface RiskMetrics {
  sharpe_ratio: number
  annualized_volatility: number
  max_drawdown: number
  max_drawdown_pct: number
  var_95: number
  var_99: number
  total_return_pct: number
  win_rate: number
  profit_factor: number
  best_day_pct: number
  worst_day_pct: number
  avg_win: number
  avg_loss: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  daily_returns: number[]
  equity_curve: number[]
  drawdown_curve: number[]
  correlation_matrix: Record<string, Record<string, number>>
}

export interface AgentData {
  id: number
  name: string
  budget: number
  max_order_notional: number
  allowed_symbols: string[]
  allowed_mcp_tools?: string[] | null
  is_active: boolean
  created_at: string
}

export interface RiskSnapshot {
  metrics: RiskMetrics
  estimated_equity: number
  gross_position_notional: number
  gross_exposure_multiple: number | null
  policy: {
    max_gross_exposure_multiple: number
    max_order_notional: number
    max_shares_per_symbol: number
    slippage_bps: number
    slippage_impact_bps_per_million: number
    max_portfolio_var_95_pct_of_equity?: number
    max_portfolio_cvar_95_pct_of_equity?: number
  }
  budget?: {
    var_95_pct_of_equity: number | null
    cvar_95_pct_of_equity: number | null
    return_sample_size: number
    sufficient_for_budget: boolean
    max_portfolio_var_95_pct_of_equity: number
    max_portfolio_cvar_95_pct_of_equity: number
    var_95_utilization?: number | null
    cvar_95_utilization?: number | null
    max_utilization?: number | null
    near_limit?: boolean
  }
  position_count: number
}

export interface RiskWhatIfResult {
  decision?: 'ALLOW' | 'REJECT' | 'RESIZE' | 'REQUIRE_APPROVAL'
  allowed: boolean
  requires_approval?: boolean
  reason: string | null
  actor?: string
  tool?: string
  agent?: AgentData | null
  requested_order?: {
    symbol: string
    side: string
    quantity: number
    order_kind: string
    limit_price: number | null
  }
  checks?: Array<{
    name: string
    passed: boolean
    detail: Record<string, unknown>
  }>
  symbol?: string
  side?: string
  order_kind?: string
  requested_quantity?: number
  adjusted_quantity?: number
  would_resize?: boolean
  estimated_mark_price?: number
  estimated_fill_price?: number
  projected_notional?: number
  estimated_fee?: number
  current_position?: number
  projected_position?: number
  estimated_equity?: number
  projected_gross_notional_before?: number
  projected_gross_notional_after?: number
  projected_gross_multiple_after?: number | null
  projected_concentration_after?: number | null
  risk_budget?: RiskSnapshot['budget']
}

export interface SimulationScenario {
  id: number
  name: string
  description: string
  legs: Array<{
    symbol: string
    side: string
    quantity: number
    order_kind?: string
    limit_price?: number | null
  }>
  created_at: string
  updated_at?: string
  current_revision?: number
  version_count?: number
}

export interface SimulationRunResult {
  scenario_name?: string | null
  summary: {
    legs: number
    allowed: number
    rejected: number
    acceptance_rate: number
    projected_notional_allowed: number
    top_rejection_reasons: Array<{ reason: string; count: number }>
  }
  results: RiskWhatIfResult[]
}

export interface SimulationCompareResult {
  baseline: {
    id: number
    name: string
    summary: SimulationRunResult['summary']
  }
  candidate: {
    id: number
    name: string
    summary: SimulationRunResult['summary']
  }
  delta: {
    acceptance_rate: number
    projected_notional_allowed: number
    rejected: number
  }
}

export interface SimulationScenarioVersion {
  id: number
  revision: number
  legs: Array<{
    symbol: string
    side: string
    quantity: number
    order_kind?: string
    limit_price?: number | null
  }>
  note: string
  created_at: string
}

export interface ReconciliationResult {
  enabled: boolean
  reason?: string
  error?: string
  ledger_positions: Record<string, number>
  broker_positions?: Record<string, number>
  mismatches?: Array<{
    symbol: string
    ledger_qty: number
    broker_qty: number
    delta: number
  }>
  in_sync?: boolean
}

export interface OrderIntent {
  id: number
  client_order_id: string
  symbol: string
  side: string
  quantity: number
  order_kind: string
  limit_price: number | null
  agent_id: number | null
  actor: string
  status: string
  reason?: string | null
  decision?: RiskWhatIfResult | null
  created_at: string
  resolved_at: string | null
}

export interface AgentAction {
  id: number
  ts: string
  agent_id: number | null
  agent_name: string | null
  actor: string
  tool: string
  action: string
  decision: string
  reason: string | null
  payload: RiskWhatIfResult
  result: Record<string, unknown> | null
}

export interface AgentStats {
  agent_id: number
  agent_name: string
  total_orders: number
  filled_orders: number
  rejected_orders: number
  total_notional: number
  total_fees: number
  realized_pnl: number
  budget_used: number
  budget_remaining: number
  positions: Record<string, number>
}

export interface ReplayState {
  event_id: number
  timestamp: string
  cash: number
  positions: Record<string, number>
  total_deposits: number
  total_orders: number
  total_fills: number
  realized_pnl: number
}

export interface BacktestResult {
  name: string
  steps: number
  final_equity: number
  total_return_pct: number
  sharpe_ratio: number
  max_drawdown_pct: number
  total_trades: number
  win_rate: number
  profit_factor: number
  equity_curve: number[]
  price_history: Record<string, number[]>
}

export interface ApiKeyData {
  id: number
  name: string
  key_prefix: string
  role: string
  is_active: boolean
  created_at: string
  raw_key?: string
}

export interface MetricsData {
  uptime_seconds: number
  total_requests: number
  total_errors: number
  error_rate: number
  requests_per_second: number
  status_codes: Record<number, number>
  top_endpoints: Array<{ path: string; count: number }>
  latency: Record<string, {
    count: number
    avg_ms: number
    p50_ms: number
    p95_ms: number
    p99_ms: number
    max_ms: number
  }>
}

export interface SweepResult {
  order_id: number
  filled: number
  remaining: number
  status: string
}

export interface AlertRule {
  id: number
  name: string
  alert_type: string
  threshold: number
  symbol: string | null
  is_active: boolean
  created_at: string
  cooldown_seconds: number
}

export interface AlertNotification {
  id: number
  alert_id: number
  alert_name: string
  message: string
  severity: string
  fired_at: string
}

export interface BacktestRun {
  id: number
  name: string
  result: BacktestResult
  created_at: string
}

export interface ResearchMetrics {
  bars: number
  total_return: number
  annualized_return: number
  annualized_volatility: number
  sharpe: number
  max_drawdown: number
  hit_rate: number
}

export interface ResearchRunSummary {
  id: number
  name: string
  strategy_name: string
  created_at: string
  metrics: ResearchMetrics
  benchmark: ResearchMetrics
  diagnostics: {
    signal_counts_by_symbol?: Record<string, number>
    direction_counts?: Record<string, number>
    avg_abs_exposure?: number
    turnover?: number
    sample_size_warning?: boolean
  }
  methodology: {
    type: string
    train_bars: number
    test_bars: number
    step_bars: number
    windows: number
    data_source: string
    seed: number
    note: string
  }
}

export interface ResearchRunDetail extends ResearchRunSummary {
  strategy: {
    name: string
    description: string
    required_history: number
    config: Record<string, unknown>
  }
  universe: string[]
  excess: ResearchMetrics
  windows: Array<{
    index: number
    train_start: string
    train_end: string
    test_start: string
    test_end: string
    signal_count: number
    turnover: number
    metrics: ResearchMetrics
  }>
  diagnostics: ResearchRunSummary['diagnostics'] & {
    latest_signals?: StrategySignal[]
  }
  equity_curve: number[]
  benchmark_curve: number[]
  config: Record<string, unknown>
}

export interface StrategyInfo {
  name: string
  description: string
  active: boolean
  required_history: number
  universe: string[]
  config: Record<string, unknown>
}

export interface StrategySignal {
  id: number
  strategy_name: string
  symbol: string
  direction: 'LONG' | 'SHORT' | 'FLAT'
  strength: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface BrokerStatusData {
  backend: string
  broker: {
    mode?: string
    connected: boolean
    equity?: number
    buying_power?: number
    cash?: number
    day_trade_count?: number
    error?: string
  }
  simulator_active: boolean
  strategy_engine_running: boolean
}

export interface ExecutionPlanData {
  symbol: string
  side: string
  total_quantity: number
  algorithm: string
  benchmark_price: number
  avg_fill_price: number
  slippage_bps: number
  implementation_shortfall: number
  completed: boolean
  slices_total: number
  slices_filled: number
  slices: Array<{
    seq: number
    qty: number
    weight: number
    target_time: string
    executed: boolean
    fill_price: number | null
  }>
}

export interface ExecutionQualityData {
  summary: {
    orders_analyzed: number
    fills_analyzed: number
    notional: number
    fees: number
    fee_bps_realized: number
    implementation_shortfall_bps: number
  }
  by_symbol: Array<{
    symbol: string
    fills: number
    notional: number
    fees: number
    fee_bps_realized: number
    avg_buy_price: number | null
    avg_sell_price: number | null
    net_quantity: number
  }>
}

export interface CausalEvent {
  id: number
  ts: string
  event_type: string
  actor: string
  agent_id: number | null
  correlation_id: string
  causation_id: number | null
  source_table: string | null
  source_id: number | null
  payload: Record<string, unknown>
  state_hash: string
}

export interface CausalChain {
  root_event_id: number
  correlation_id: string
  events: CausalEvent[]
  graph: {
    nodes: Array<{
      id: number
      label: string
      actor: string
      agent_id: number | null
      state_hash: string
    }>
    edges: Array<{ from: number; to: number; type: string }>
  }
  integrity: {
    ok: boolean
    checked_events: number
    head_hash?: string
    failed_event_id?: number
  }
}

export interface CausalReplaySummary {
  to_event_id: number | null
  total_events: number
  event_counts: Record<string, number>
  agent_decisions: Record<string, number>
  correlation_count: number
  integrity: {
    ok: boolean
    checked_events: number
    head_hash?: string
  }
}

export interface CausalCounterfactual {
  policy: {
    max_order_notional: number | null
    max_gross_exposure_multiple: number | null
    require_approval_for_all_agents: boolean
  }
  events_evaluated: number
  changed_decisions: number
  changes: Array<{
    event_id: number
    ts: string
    event_type: string
    correlation_id: string
    original_decision: string
    counterfactual_decision: string
    reasons: string[]
    symbol?: string
    side?: string
    projected_notional: number
    projected_gross_multiple_after?: number | null
  }>
}

export interface VenueOrder {
  id: number
  client_order_id: string
  symbol: string
  side: string
  quantity: number
  order_type: string
  limit_price: number | null
  time_in_force: string
  status: string
  filled_quantity: number
  remaining_quantity: number
  avg_fill_price: number | null
  expires_at_tick: number | null
  current_tick: number
  latency_ticks_remaining: number
  created_at: string
  updated_at: string
  fills: Array<{
    id: number
    quantity: number
    price: number
    spread_bps: number
    impact_bps: number
    tick: number
    created_at: string
  }>
}

export interface VenueStatus {
  mode: string
  config: {
    base_spread_bps: number
    impact_bps_per_1000_shares: number
    depth_per_tick: number
    latency_ticks: number
    default_tif_ticks: number
  }
  orders_by_status: Record<string, number>
  fills: {
    count: number
    quantity: number
    avg_spread_bps: number
    avg_impact_bps: number
  }
}
