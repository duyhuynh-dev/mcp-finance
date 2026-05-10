# Agent Control Plane

Local MCP-native control plane for testing AI-agent trading actions under **policy checks**, **risk explanations**, **human approval**, **simulated execution**, and **audit replay**.

## Requirements

- Python **3.11+** (required for `StrEnum`, `mcp`, and typed stacks).
- Node 20+ for the web UI.

## Setup

```bash
cd ai-project
python3.11 -m pip install -e ".[dev]"
npm run install:web
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `FINANCE_DB_PATH` | `./data/finance.db` | SQLite file shared by API + portfolio MCP |
| `FINANCE_QUOTE_BACKEND` | `mock` | `mock` (CI/tests) or `yahoo` (live last price, no API key) |
| `CORS_ORIGINS` | localhost dev | Comma-separated origins for FastAPI |

## Run the API (dashboard backend)

```bash
export FINANCE_DB_PATH="$PWD/data/finance.db"
python3.11 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

## Run the web UI

From the **repo root**:

```bash
npm run dev
```

Or: `cd web && npm run dev`.

Open **http://127.0.0.1:5173**. Vite proxies `/api` to **8001**.

You need **two** processes: `uvicorn` (8001) and **`npm run dev`** (5173).

## Eval scenarios (agent regression)

JSON files in `scenarios/eval/` are run by `finance_core.eval_runner` (see `tests/test_eval_scenarios.py`).

```bash
python3.11 scripts/run_eval.py
```

## MCP servers (Cursor / Claude Desktop)

Use the same `FINANCE_DB_PATH` as the API. Optional: `FINANCE_QUOTE_BACKEND=yahoo` for live quotes in MCP.

```json
{
  "mcpServers": {
    "finance-market": {
      "command": "python3.11",
      "args": ["/absolute/path/to/ai-project/servers/market_mcp.py"],
      "env": {}
    },
    "finance-portfolio": {
      "command": "python3.11",
      "args": ["/absolute/path/to/ai-project/servers/portfolio_mcp.py"],
      "env": {
        "FINANCE_DB_PATH": "/absolute/path/to/ai-project/data/finance.db"
      }
    }
  }
}
```

**Tools:** `get_quote`, `list_symbols` · `get_state`, `place_order` (optional `order_kind` MARKET/LIMIT, `limit_price`), `cancel_order`, `list_recent_orders`, `list_recent_fills`, `get_risk_metrics`, agents + backtest helpers.

**Quant / ML (same DB as the API):** `list_quant_strategies`, `set_quant_strategy_active`, `run_quant_strategies_once`, `list_quant_signals`, `start_quant_engine`, `stop_quant_engine`, `get_quant_engine_status`, `finance_stack_health`, `get_ml_alpha_diagnostics`, `get_strategy_diagnostics`, `get_risk_snapshot`, `stress_portfolio`, `reconcile_ledger_vs_broker`, `forward_strategy_signals_to_alpaca` (needs `SIGNALS_TO_ALPACA=1`), `create_pending_order_intent`, `list_pending_order_intents`, `approve_pending_order_intent`. Agents may set `allowed_mcp_tools` (JSON array) to restrict those tools when using `agent_id`.

**REST (selected):** `GET /api/risk/snapshot`, `POST /api/risk/stress`, `GET /api/broker/reconciliation`, `GET /api/execution-events`, `GET /api/execution-events/replay`, `POST /api/order-intents`, `GET /api/order-intents/pending`, `POST /api/order-intents/{id}/approve|reject`, `POST /api/strategies/forward-signals-alpaca` (flagged). Policy: `max_gross_exposure_multiple`, `slippage_impact_bps_per_million`. Env: `HEALTH_CHECK_ALPACA`, `SIGNALS_TO_ALPACA`, `BROKER_EXECUTION_MODE` (`internal` or `alpaca_paper`) (see `.env.example`).

See `IMPLEMENTATION_PLAN.md` for what is shipped vs optional next steps.

## Scripted demo (no LLM)

```bash
export FINANCE_DB_PATH="$PWD/data/finance.db"
python3.11 scripts/demo_scenario.py
```

## Tests & CI

```bash
python3.11 -m pytest tests/ -v
ruff check api packages/core servers scripts tests
```

`GET /api/health` checks SQLite (`SELECT 1`) and reports whether the strategy engine thread is running; returns **503** if the database check fails. CI runs the full suite (including MCP import smoke and `ml_alpha` holdout metrics tests).

GitHub Actions (`.github/workflows/ci.yml`): **ruff**, **pytest** (`FINANCE_QUOTE_BACKEND=mock`), **web build**.

## Production Docker Deploy

```bash
docker build -t agent-control-plane .
docker run --rm \
  -e FINANCE_DB_PATH=/app/data/finance.db \
  -e FINANCE_QUOTE_BACKEND=mock \
  -e REQUIRE_AUTH=false \
  -p 8000:8000 \
  -v agent-control-plane-data:/app/data \
  agent-control-plane
```

The container serves the landing page, React app, API, WebSocket, and static assets from one origin:

- Landing page: `http://localhost:8000/`
- App: `http://localhost:8000/app`
- Health check: `http://localhost:8000/api/health`

For a quick public deploy, use the included `render.yaml` blueprint. Create a new Render Blueprint from this GitHub repo; Render will build the Dockerfile, attach a persistent disk at `/app/data`, and use `/api/health` as the health check.

## Security

See **[SECURITY.md](./SECURITY.md)** for trust boundaries and demo limitations.

## Layout

| Path | Role |
|------|------|
| `packages/core/finance_core/` | Ledger, policy, quotes, audit, eval runner |
| `scenarios/eval/` | JSON eval scenarios |
| `servers/` | MCP stdio servers |
| `api/` | FastAPI REST for the UI |
| `web/` | Vite + React dashboard |
| `scripts/demo_scenario.py` | Seed + trades |
| `scripts/run_eval.py` | Run eval JSON suite |
