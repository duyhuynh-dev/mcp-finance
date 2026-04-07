# Implementation plan

## Shipped in core

- **Execution / microstructure:** size-aware slippage via `slippage_impact_bps_per_million` on `PolicyRules`; optional **signals → Alpaca paper** (`SIGNALS_TO_ALPACA=1`, API + MCP); **ledger vs Alpaca reconciliation** when quotes are Alpaca-backed (`GET /api/broker/reconciliation`, MCP `reconcile_ledger_vs_broker`).
- **Risk:** **pre-trade gross exposure** cap with reduce-to-fit (`max_gross_exposure_multiple` on `PolicyRules`, rejection `PRE_TRADE_GROSS_EXPOSURE`); **stress** endpoint (`POST /api/risk/stress`, MCP `stress_portfolio`); **unified snapshot** (`GET /api/risk/snapshot`, MCP `get_risk_snapshot`).
- **Agent governance:** `allowed_mcp_tools` on agents (JSON list; `null` = all tools); MCP gates `place_order`, `cancel_order`, `run_quant_strategies_once`, `start_quant_engine`, `stop_quant_engine`, `forward_strategy_signals_to_alpaca` when `agent_id` is set.
- **Human-in-the-loop:** `order_intents` table; `POST /api/order-intents`, list pending, approve (requires `manage_agents`) / reject; MCP `create_pending_order_intent`, `list_pending_order_intents`, `approve_pending_order_intent`.
- **Reliability:** `request_id` on audit payloads and WebSocket events (from API context); **`HEALTH_CHECK_ALPACA`** optional block on `/api/health`.
- **Research / ML:** `ml_alpha` holdout metrics + methodology in diagnostics; intraday bars remain **provider-dependent** (extend `get_historical_bars` / entitlements per broker). Optional **replication notebook** still a nice-to-have.

## Follow-ups (prioritize as needed)

- Deeper **pre-trade** (sector limits, VaR budget, structured “resize” reasons in API).
- **Reconciliation UI** panel and automated drift alerts.
- **HIL UI** in the dashboard for intent queue.
- **MCP tool matrix** UI when registering agents.
- Full **walk-forward ML** reports (rolling windows, calibration plots) beyond single holdout metrics.
- **Classic paper replication** notebook (pairs / momentum).

Update this file when you ship or reprioritize.
