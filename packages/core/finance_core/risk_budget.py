"""VaR/CVaR from equity snapshots vs optional policy caps (gross-scaled proxy)."""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from finance_core.policy import PolicyRules
from finance_core.pre_trade_risk import _gross_after_order, _gross_notional
from finance_core.types import OrderSide, Position, RejectionReason

MIN_RETURNS_FOR_BUDGET = 10
_MAX_GROSS_SCALE = 10.0
NEAR_LIMIT_UTILIZATION = 0.8


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = pct * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def equity_returns_from_equities(equities: list[float]) -> list[float]:
    returns: list[float] = []
    for i in range(1, len(equities)):
        if equities[i - 1] > 1e-9:
            returns.append((equities[i] - equities[i - 1]) / equities[i - 1])
    return returns


def equity_returns_from_conn(conn: sqlite3.Connection) -> list[float]:
    rows = conn.execute(
        "SELECT equity FROM equity_snapshots ORDER BY id ASC"
    ).fetchall()
    eq = [float(r["equity"]) for r in rows]
    return equity_returns_from_equities(eq)


def var_cvar_95_pct_from_returns(returns: list[float]) -> tuple[float, float]:
    """VaR(95) and CVaR(95) as positive loss fractions (aligned with risk.compute)."""
    if len(returns) < MIN_RETURNS_FOR_BUDGET:
        return 0.0, 0.0
    sr = sorted(returns)
    var_pct = abs(_percentile(sr, 0.05))
    k = max(1, int(0.05 * len(sr)))
    tail = sr[:k]
    cvar_pct = abs(sum(tail) / len(tail))
    return var_pct, cvar_pct


def portfolio_var_cvar_metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    returns = equity_returns_from_conn(conn)
    sufficient = len(returns) >= MIN_RETURNS_FOR_BUDGET
    var_pct, cvar_pct = var_cvar_95_pct_from_returns(returns)
    return {
        "var_95_pct_of_equity": round(var_pct, 6) if sufficient else None,
        "cvar_95_pct_of_equity": round(cvar_pct, 6) if sufficient else None,
        "return_sample_size": len(returns),
        "sufficient_for_budget": sufficient,
    }


def build_risk_budget_section(
    conn: sqlite3.Connection, rules: PolicyRules,
) -> dict[str, Any]:
    m = portfolio_var_cvar_metrics(conn)
    var_pct = m["var_95_pct_of_equity"]
    cvar_pct = m["cvar_95_pct_of_equity"]
    var_cap = rules.max_portfolio_var_95_pct_of_equity
    cvar_cap = rules.max_portfolio_cvar_95_pct_of_equity
    var_util = (var_pct / var_cap) if (var_pct is not None and var_cap > 0) else None
    cvar_util = (
        (cvar_pct / cvar_cap) if (cvar_pct is not None and cvar_cap > 0) else None
    )
    max_util = None
    vals = [v for v in (var_util, cvar_util) if v is not None]
    if vals:
        max_util = max(vals)
    return {
        **m,
        "max_portfolio_var_95_pct_of_equity": var_cap,
        "max_portfolio_cvar_95_pct_of_equity": (
            cvar_cap
        ),
        "var_95_utilization": round(var_util, 4) if var_util is not None else None,
        "cvar_95_utilization": (
            round(cvar_util, 4) if cvar_util is not None else None
        ),
        "max_utilization": round(max_util, 4) if max_util is not None else None,
        "near_limit": bool(max_util is not None and max_util >= NEAR_LIMIT_UTILIZATION),
    }


def check_var_cvar_budget(
    conn: sqlite3.Connection,
    rules: PolicyRules,
    positions: dict[str, Position],
    symbol: str,
    side: OrderSide,
    quantity: float,
    price: float,
) -> RejectionReason | None:
    if (
        rules.max_portfolio_var_95_pct_of_equity <= 0
        and rules.max_portfolio_cvar_95_pct_of_equity <= 0
    ):
        return None
    returns = equity_returns_from_conn(conn)
    if len(returns) < MIN_RETURNS_FOR_BUDGET:
        return None
    var_pct, cvar_pct = var_cvar_95_pct_from_returns(returns)
    gross_now = _gross_notional(positions)
    gross_after = _gross_after_order(
        gross_now, symbol, side, quantity, price, positions,
    )
    if gross_now < 1e-9:
        scale = 1.0
    else:
        scale = min(gross_after / gross_now, _MAX_GROSS_SCALE)

    if rules.max_portfolio_var_95_pct_of_equity > 0:
        if var_pct * scale > rules.max_portfolio_var_95_pct_of_equity + 1e-12:
            return RejectionReason.MAX_VAR_BUDGET
    if rules.max_portfolio_cvar_95_pct_of_equity > 0:
        if cvar_pct * scale > rules.max_portfolio_cvar_95_pct_of_equity + 1e-12:
            return RejectionReason.MAX_CVAR_BUDGET
    return None
