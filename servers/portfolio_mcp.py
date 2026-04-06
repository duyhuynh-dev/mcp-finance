#!/usr/bin/env python3
"""MCP server: paper portfolio (orders, fills, policy, risk, agents). Uses FINANCE_DB_PATH."""

from __future__ import annotations

import os
import sys
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "packages", "core"))

from finance_core.agents import AgentManager
from finance_core.audit import list_audit
from finance_core.backtest import BacktestConfig, run_backtest
from finance_core.ledger import Ledger
from finance_core.quote_factory import create_quote_provider
from finance_core.risk import compute_risk_metrics
from finance_core.types import OrderKind, OrderSide
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("finance-portfolio")

_ledger: Ledger | None = None
_strategy_engine = None


def _db_path() -> str:
    return os.environ.get(
        "FINANCE_DB_PATH", os.path.join(_ROOT, "data", "finance.db")
    )


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        _ledger = Ledger.open(_db_path(), quotes=create_quote_provider())
    return _ledger


def get_strategy_engine():
    """Lazy StrategyEngine sharing DB + quotes with the ledger (MCP process)."""
    global _strategy_engine
    if _strategy_engine is None:
        from finance_core.strategies.factory import build_default_strategy_engine

        lg = get_ledger()
        _strategy_engine = build_default_strategy_engine(
            lg.conn, lg.quotes, interval=60.0,
        )
    return _strategy_engine


@mcp.tool()
def get_state() -> dict:
    """Current cash, positions with P&L, trading_enabled, and policy rules."""
    ledger = get_ledger()
    s = ledger.portfolio_state()
    pr = ledger.policy_engine.rules
    return {
        "cash": s.cash,
        "trading_enabled": s.trading_enabled,
        "total_realized_pnl": s.total_realized_pnl,
        "total_unrealized_pnl": s.total_unrealized_pnl,
        "positions": {
            k: {
                "quantity": v.quantity, "avg_cost": v.avg_cost,
                "mark_price": v.mark_price, "market_value": v.market_value,
                "unrealized_pnl": v.unrealized_pnl,
            }
            for k, v in s.positions.items()
        },
        "rules_version": s.rules_version,
        "max_shares_per_symbol": pr.max_shares_per_symbol,
        "max_order_notional": pr.max_order_notional,
        "fee_bps": pr.fee_bps,
        "slippage_bps": pr.slippage_bps,
    }


@mcp.tool()
def place_order(
    client_order_id: str, symbol: str, side: str, quantity: float,
    order_kind: str = "MARKET", limit_price: float | None = None,
    agent_id: int | None = None,
) -> dict:
    """Place a paper order. Idempotent on client_order_id."""
    ledger = get_ledger()
    s = OrderSide(side.strip().upper())
    k = OrderKind(order_kind.strip().upper())
    lp = float(limit_price) if limit_price is not None else None
    r = ledger.place_order(
        client_order_id.strip(), symbol, s, float(quantity),
        order_kind=k, limit_price=lp, actor="mcp",
        agent_id=int(agent_id) if agent_id is not None else None,
    )
    return r.to_audit_dict()


@mcp.tool()
def cancel_order(order_id: int) -> dict:
    """Cancel a PENDING limit order by order id."""
    return get_ledger().cancel_order(int(order_id), actor="mcp")


@mcp.tool()
def deposit(amount: float) -> dict:
    """Deposit cash into the paper account."""
    cash = get_ledger().deposit(float(amount), actor="mcp")
    return {"cash": cash}


@mcp.tool()
def set_trading_enabled(enabled: bool) -> dict:
    """Enable or disable the kill switch."""
    get_ledger().set_trading_enabled(bool(enabled), actor="mcp")
    return {"trading_enabled": enabled}


@mcp.tool()
def list_audit_events(limit: int = 30) -> list[dict]:
    """Recent audit trail entries."""
    return list_audit(get_ledger().conn, limit=min(int(limit), 100))


@mcp.tool()
def list_recent_orders(limit: int = 20) -> list[dict]:
    """Recent orders newest first."""
    rows = get_ledger().list_orders(limit=min(int(limit), 100))
    return [
        {
            "id": o.id, "client_order_id": o.client_order_id,
            "symbol": o.symbol, "side": o.side.value,
            "quantity": o.quantity, "status": o.status.value,
            "rejection_reason": o.rejection_reason.value if o.rejection_reason else None,
            "order_kind": o.order_kind.value, "limit_price": o.limit_price,
            "created_at": o.created_at.isoformat(),
        }
        for o in rows
    ]


@mcp.tool()
def list_recent_fills(limit: int = 20) -> list[dict]:
    """Recent fills newest first."""
    rows = get_ledger().list_fills(limit=min(int(limit), 100))
    return [
        {
            "id": f.id, "order_id": f.order_id, "symbol": f.symbol,
            "side": f.side.value, "quantity": f.quantity,
            "price": f.price, "fee": f.fee,
            "realized_pnl": f.realized_pnl,
            "filled_at": f.filled_at.isoformat(),
        }
        for f in rows
    ]


@mcp.tool()
def get_risk_metrics() -> dict:
    """Portfolio risk analytics: Sharpe, drawdown, VaR, win rate."""
    m = compute_risk_metrics(get_ledger().conn)
    return m.to_dict()


@mcp.tool()
def register_agent(
    name: str, budget: float, allowed_symbols: str = "",
) -> dict:
    """Register a named agent with budget and optional symbol restrictions (comma-separated)."""
    syms = (
        [s.strip().upper() for s in allowed_symbols.split(",") if s.strip()]
        if allowed_symbols
        else None
    )
    mgr = AgentManager(get_ledger().conn)
    agent = mgr.register(name, float(budget), allowed_symbols=syms)
    return agent.to_dict()


@mcp.tool()
def list_agents() -> list[dict]:
    """List all registered agents."""
    mgr = AgentManager(get_ledger().conn)
    return [a.to_dict() for a in mgr.list_all()]


@mcp.tool()
def agent_stats(agent_id: int) -> dict:
    """Get trading stats for a specific agent."""
    mgr = AgentManager(get_ledger().conn)
    s = mgr.stats(int(agent_id))
    return s.to_dict() if s else {"error": "agent not found"}


@mcp.tool()
def list_quant_strategies() -> list[dict]:
    """List registered quant strategies (momentum, mean reversion, ml_alpha, etc.)."""
    return get_strategy_engine().list_strategies()


@mcp.tool()
def set_quant_strategy_active(strategy_name: str, active: bool) -> dict:
    """Enable or disable a strategy by name for the next run_quant_strategies_once call."""
    engine = get_strategy_engine()
    name = strategy_name.strip()
    if engine.get_strategy(name) is None:
        return {"error": f"unknown strategy: {name}", "active": False}
    if active:
        engine.activate(name)
    else:
        engine.deactivate(name)
    return {"name": name, "active": bool(active)}


@mcp.tool()
def run_quant_strategies_once() -> dict:
    """Run all active strategies once; persist signals to DB. Returns signal dicts."""
    signals = get_strategy_engine().run_once()
    return {
        "count": len(signals),
        "signals": [s.to_dict() for s in signals],
    }


@mcp.tool()
def list_quant_signals(strategy_name: str = "", limit: int = 50) -> list[dict]:
    """Recent signals from SQLite; pass empty strategy_name for all strategies."""
    engine = get_strategy_engine()
    name = strategy_name.strip() or None
    return engine.recent_signals(name, limit=min(int(limit), 200))


@mcp.tool()
def get_ml_alpha_diagnostics() -> dict:
    """ML alpha strategy: config, feature set, per-symbol GradientBoosting importances."""
    engine = get_strategy_engine()
    strat = engine.get_strategy("ml_alpha")
    if strat is None:
        return {"error": "ml_alpha strategy not registered"}
    return strat.export_diagnostics()


@mcp.tool()
def get_strategy_diagnostics(strategy_name: str) -> dict:
    """Diagnostics for any strategy that implements export_diagnostics (e.g. ml_alpha)."""
    engine = get_strategy_engine()
    name = strategy_name.strip()
    strat = engine.get_strategy(name)
    if strat is None:
        return {"error": f"unknown strategy: {name}"}
    export = getattr(strat, "export_diagnostics", None)
    if not callable(export):
        return {"error": "diagnostics not available for this strategy", "name": name}
    return export()


@mcp.tool()
def start_quant_engine() -> dict:
    """Start the background strategy engine loop (parity with POST /api/strategies/start-engine)."""
    get_strategy_engine().start()
    return {"status": "running"}


@mcp.tool()
def stop_quant_engine() -> dict:
    """Stop the background strategy engine loop."""
    get_strategy_engine().stop()
    return {"status": "stopped"}


@mcp.tool()
def get_quant_engine_status() -> dict:
    """Whether the quant strategy engine background thread is running."""
    eng = get_strategy_engine()
    return {
        "initialized": eng is not None,
        "running": eng.is_running if eng else False,
    }


@mcp.tool()
def finance_stack_health() -> dict:
    """SQLite reachability and strategy engine state for this MCP process."""
    out: dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "strategy_engine": {"initialized": False, "running": False},
    }
    try:
        get_ledger().conn.execute("SELECT 1").fetchone()
        out["database"] = "ok"
    except Exception as exc:
        out["database"] = "error"
        out["status"] = "unhealthy"
        out["database_error"] = str(exc)[:200]
    try:
        eng = get_strategy_engine()
        if eng is not None:
            out["strategy_engine"] = {
                "initialized": True,
                "running": eng.is_running,
            }
    except Exception:
        pass
    return out


@mcp.tool()
def run_backtest_scenario(
    name: str = "bt",
    initial_cash: float = 100_000,
    steps: int = 100,
    seed: int = 42,
    rules_json: str = "[]",
) -> dict:
    """Run a backtest with synthetic prices. rules_json is a JSON array of rule objects."""
    import json
    rules = json.loads(rules_json)
    config = BacktestConfig.from_dict({
        "name": name, "initial_cash": initial_cash,
        "steps": steps, "seed": seed, "rules": rules,
    })
    return run_backtest(config).to_dict()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
