# Security model (paper trading stack)

This project is a **local / demo** system. Treat it as **untrusted if exposed to the internet** without hardening.

## Trust boundaries

- **MCP servers** run as separate processes with file-system access to `FINANCE_DB_PATH`. Anyone who can edit MCP config can point agents at a malicious binary or database path.
- **FastAPI** has **no authentication** in the default configuration. Do not bind `0.0.0.0:8001` on a public network without TLS and auth.
- **Secrets**: market APIs that need keys belong in **environment variables** on the host, never in prompts or committed `.env` files.

## What the agent cannot do (by design)

- The LLM does **not** receive raw SQL or direct DB handles; it uses **MCP tools** / REST that map to `finance_core` operations.
- **Policy** (max notional, max position, kill switch) is enforced in the ledger path, not in the model’s prose.
- **Idempotent** `client_order_id` prevents duplicate execution on retries.

## What is still your responsibility

- **Prompt injection** can make an agent *attempt* destructive or wasteful sequences of *allowed* tool calls (e.g. many small trades). Mitigate with rate limits, budgets, and human approval for large actions (not implemented in the demo).
- **SQLite file permissions**: protect the DB file from other local users if the machine is shared.

## Reporting

For vulnerabilities in **this repository’s code**, open an issue or PR; there is no private bug bounty for this demo project.
