#!/usr/bin/env python3
"""MCP server: paper portfolio (orders, fills, policy). Uses FINANCE_DB_PATH."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "packages", "core"))

from finance_core.ledger import Ledger
from finance_core.quote_factory import create_quote_provider
from finance_core.types import OrderKind, OrderSide
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("finance-portfolio")

_ledger: Ledger | None = None


def _db_path() -> str:
    return os.environ.get("FINANCE_DB_PATH", os.path.join(_ROOT, "data", "finance.db"))


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        _ledger = Ledger.open(_db_path(), quotes=create_quote_provider())
    return _ledger


@mcp.tool()
def get_state() -> dict:
    """Current cash, trading_enabled, positions, and policy rules version."""
    ledger = get_ledger()
    s = ledger.portfolio_state()
    pr = ledger.policy_engine.rules
    return {
        "cash": s.cash,
        "trading_enabled": s.trading_enabled,
        "positions": {k: {"quantity": v.quantity} for k, v in s.positions.items()},
        "rules_version": s.rules_version,
        "max_shares_per_symbol": pr.max_shares_per_symbol,
        "max_order_notional": pr.max_order_notional,
        "fee_bps": pr.fee_bps,
    }


@mcp.tool()
def place_order(
    client_order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    order_kind: str = "MARKET",
    limit_price: float | None = None,
) -> dict:
    """
    Place a paper order. Idempotent on client_order_id.
    order_kind MARKET (default) or LIMIT; for LIMIT pass limit_price.
    """
    ledger = get_ledger()
    s = OrderSide(side.strip().upper())
    k = OrderKind(order_kind.strip().upper())
    lp = float(limit_price) if limit_price is not None else None
    r = ledger.place_order(
        client_order_id.strip(),
        symbol,
        s,
        float(quantity),
        order_kind=k,
        limit_price=lp,
        actor="mcp",
    )
    return r.to_audit_dict()


@mcp.tool()
def cancel_order(order_id: int) -> dict:
    """Cancel a PENDING limit order by order id."""
    return get_ledger().cancel_order(int(order_id), actor="mcp")


@mcp.tool()
def list_recent_orders(limit: int = 20) -> list[dict]:
    """Recent orders newest first."""
    rows = get_ledger().list_orders(limit=min(int(limit), 100))
    return [
        {
            "id": o.id,
            "client_order_id": o.client_order_id,
            "symbol": o.symbol,
            "side": o.side.value,
            "quantity": o.quantity,
            "status": o.status.value,
            "rejection_reason": o.rejection_reason.value if o.rejection_reason else None,
            "order_kind": o.order_kind.value,
            "limit_price": o.limit_price,
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
            "id": f.id,
            "order_id": f.order_id,
            "symbol": f.symbol,
            "side": f.side.value,
            "quantity": f.quantity,
            "price": f.price,
            "fee": f.fee,
            "filled_at": f.filled_at.isoformat(),
        }
        for f in rows
    ]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
