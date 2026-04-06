# Implementation plan (deferred)

Priorities shipped first: **ML + MCP** (quant tools on `finance-portfolio`, shared `build_default_strategy_engine`, `get_ml_alpha_diagnostics`).

The items below are intentional follow-ups—not blockers.

## Execution & microstructure

- Pre-trade impact / size-aware slippage beyond fixed bps
- Optional **signals → Alpaca paper** path (feature flag, audit, caps)
- Internal vs broker **reconciliation** panel

## Risk subsystem

- Dedicated **pre-trade risk** pipeline (structured pass / reduce / reject)
- Stress scenarios on the book (shock vectors)
- Real-time **risk snapshot** shared by API, UI, and MCP

## Agent governance

- MCP **capability matrix** per `agent_id` (tools, notional caps, symbols)
- **Human-in-the-loop** `OrderIntent` → approve step before broker send

## Reliability & observability

- CI **smoke tests**: MCP module load, `get_state`, one `GET /api/health`
- **`GET /api/health`**: DB + optional Alpaca ping
- End-to-end **request id** through ledger audit and WS events

## UX

- Friendly **API down** state (backend not on `:8001`)
- WebSocket **reconnect** with backoff

## Research / quant depth

- Intraday bars where data entitlements allow
- Walk-forward **ML calibration** metrics (Brier, reliability)
- Optional replication notebook for one classic paper (pairs, momentum, etc.)

---

Update this file as you ship items or reprioritize.
