# Finance Stack

Paper-trading ledger with **policy checks**, **fees**, **limit orders + cancel**, **MCP tool servers**, and a **React dashboard** backed by the same SQLite database.

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

**Tools:** `get_quote`, `list_symbols` · `get_state`, `place_order` (optional `order_kind` MARKET/LIMIT, `limit_price`), `cancel_order`, `list_recent_orders`, `list_recent_fills`.

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

GitHub Actions (`.github/workflows/ci.yml`): **ruff**, **pytest** (`FINANCE_QUOTE_BACKEND=mock`), **web build**.

## Docker (API only)

```bash
docker build -t finance-stack-api .
docker run --rm -e FINANCE_DB_PATH=/data/finance.db -p 8001:8001 finance-stack-api
```

Serves FastAPI on port 8001. Build the web app separately (`cd web && npm run build`) and serve `web/dist` with any static host or point the UI at this API.

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
