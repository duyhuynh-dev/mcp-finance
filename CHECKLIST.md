# Project checklist (task-based)

## Definition of done

- [x] Single SQLite + `finance_core`; MCP + API + UI share state
- [x] Agent path: MCP tools + policy + idempotent orders + fees + LIMIT + cancel
- [x] Human path: FastAPI + dashboard
- [x] Proof: pytest (ledger, API, eval JSON, Yahoo mock, fee/limit)
- [x] Docs: README, SECURITY.md, Docker, CI

## Phases

- [x] Phase 0 — Repo skeleton, packaging, web, env
- [x] Phase 1 — Ledger, schema, migrations
- [x] Phase 2 — Policy (+ `fee_bps`)
- [x] Phase 3 — Mock + optional Yahoo quotes (`FINANCE_QUOTE_BACKEND`)
- [x] Phase 4 — MCP market + portfolio (+ cancel, LIMIT params)
- [x] Phase 5 — Audit trail
- [x] Phase 6 — FastAPI (+ `/api/cancel-order/{id}`)
- [x] Phase 7 — Dashboard (policy fee, fill fees, cancel PENDING)
- [x] Phase 8 — `demo_scenario.py`, `run_eval.py`, ruff
- [x] Eval harness — `scenarios/eval/*.json` + `eval_runner`
- [x] CI — GitHub Actions
- [x] SECURITY.md
- [x] Dockerfile

## Backlog (optional next)

- [ ] Broker API with API keys (Alpaca, etc.) behind `QuoteProvider`
- [ ] Partial fills / order book
- [ ] Rate limits / agent budgets
- [ ] Hosted deploy (Fly/Railway) with auth
