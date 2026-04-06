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
  max_daily_order_count: number
  max_portfolio_concentration_pct: number
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
  is_active: boolean
  created_at: string
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
