"""Portfolio risk analytics: Sharpe, drawdown, VaR, volatility, win rate."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from finance_core.risk_budget import build_risk_budget_section


@dataclass
class RiskMetrics:
    sharpe_ratio: float = 0.0
    annualized_volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    best_day_pct: float = 0.0
    worst_day_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    daily_returns: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        def _safe(v: float) -> float:
            if math.isinf(v) or math.isnan(v):
                return 9999.99
            return v

        return {
            "sharpe_ratio": round(_safe(self.sharpe_ratio), 4),
            "annualized_volatility": round(_safe(self.annualized_volatility), 4),
            "max_drawdown": round(_safe(self.max_drawdown), 2),
            "max_drawdown_pct": round(_safe(self.max_drawdown_pct), 4),
            "var_95": round(_safe(self.var_95), 2),
            "var_99": round(_safe(self.var_99), 2),
            "total_return_pct": round(_safe(self.total_return_pct), 4),
            "win_rate": round(_safe(self.win_rate), 4),
            "profit_factor": round(_safe(self.profit_factor), 4),
            "best_day_pct": round(_safe(self.best_day_pct), 4),
            "worst_day_pct": round(_safe(self.worst_day_pct), 4),
            "avg_win": round(_safe(self.avg_win), 2),
            "avg_loss": round(_safe(self.avg_loss), 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "daily_returns": [round(r, 6) for r in self.daily_returns[-60:]],
            "equity_curve": [round(e, 2) for e in self.equity_curve[-120:]],
            "drawdown_curve": [round(d, 4) for d in self.drawdown_curve[-120:]],
            "correlation_matrix": self.correlation_matrix,
        }


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = pct * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def compute_risk_metrics(conn: sqlite3.Connection) -> RiskMetrics:
    m = RiskMetrics()

    equities = conn.execute(
        "SELECT equity FROM equity_snapshots ORDER BY id ASC"
    ).fetchall()
    eq = [float(r["equity"]) for r in equities]
    m.equity_curve = eq

    if len(eq) >= 2:
        m.total_return_pct = (eq[-1] - eq[0]) / eq[0] if eq[0] != 0 else 0.0

        returns: list[float] = []
        for i in range(1, len(eq)):
            if eq[i - 1] > 1e-9:
                returns.append((eq[i] - eq[i - 1]) / eq[i - 1])
        m.daily_returns = returns

        if returns:
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
            std_r = math.sqrt(var_r) if var_r > 0 else 0.0

            m.annualized_volatility = std_r * math.sqrt(252)
            m.sharpe_ratio = (
                (mean_r / std_r) * math.sqrt(252) if std_r > 1e-12 else 0.0
            )
            m.best_day_pct = max(returns)
            m.worst_day_pct = min(returns)

            sr = sorted(returns)
            current_eq = eq[-1]
            m.var_95 = abs(_percentile(sr, 0.05)) * current_eq
            m.var_99 = abs(_percentile(sr, 0.01)) * current_eq

        peak = eq[0]
        dd_curve: list[float] = []
        max_dd = 0.0
        max_dd_pct = 0.0
        for e in eq:
            if e > peak:
                peak = e
            dd = peak - e
            dd_pct = dd / peak if peak > 0 else 0.0
            dd_curve.append(dd_pct)
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
        m.drawdown_curve = dd_curve
        m.max_drawdown = max_dd
        m.max_drawdown_pct = max_dd_pct

    sells = conn.execute(
        "SELECT realized_pnl FROM fills WHERE side = 'SELL'"
    ).fetchall()
    if sells:
        pnls = [float(r["realized_pnl"]) for r in sells]
        m.total_trades = len(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        m.winning_trades = len(wins)
        m.losing_trades = len(losses)
        m.win_rate = len(wins) / len(pnls) if pnls else 0.0
        m.avg_win = sum(wins) / len(wins) if wins else 0.0
        m.avg_loss = sum(losses) / len(losses) if losses else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        m.profit_factor = (
            gross_profit / gross_loss if gross_loss > 1e-9 else float("inf")
        )

    m.correlation_matrix = _symbol_correlation(conn)
    return m


def _symbol_correlation(conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
    """Pairwise return correlation between symbols from fill prices."""
    rows = conn.execute(
        """
        SELECT symbol, price, filled_at FROM fills
        WHERE side = 'BUY'
        ORDER BY filled_at ASC
        """
    ).fetchall()
    by_sym: dict[str, list[float]] = {}
    for r in rows:
        sym = r["symbol"]
        by_sym.setdefault(sym, []).append(float(r["price"]))

    returns_by_sym: dict[str, list[float]] = {}
    for sym, prices in by_sym.items():
        if len(prices) >= 2:
            rets = []
            for i in range(1, len(prices)):
                if prices[i - 1] > 1e-9:
                    rets.append((prices[i] - prices[i - 1]) / prices[i - 1])
            if rets:
                returns_by_sym[sym] = rets

    syms = sorted(returns_by_sym.keys())
    matrix: dict[str, dict[str, float]] = {}
    for a in syms:
        matrix[a] = {}
        for b in syms:
            matrix[a][b] = _corr(returns_by_sym[a], returns_by_sym[b])
    return matrix


def _corr(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n
    sx = math.sqrt(sum((xs[i] - mx) ** 2 for i in range(n)) / n)
    sy = math.sqrt(sum((ys[i] - my) ** 2 for i in range(n)) / n)
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return round(cov / (sx * sy), 4)


def build_risk_snapshot(conn: sqlite3.Connection, ledger: Any) -> dict[str, Any]:
    """Single payload: historical risk metrics + live book + policy caps."""
    metrics = compute_risk_metrics(conn).to_dict()
    ps = ledger.portfolio_state()
    rules = ledger.policy_engine.rules
    eq = ledger.estimated_equity()
    gross = sum(abs(p.market_value) for p in ps.positions.values())
    return {
        "metrics": metrics,
        "estimated_equity": round(eq, 2),
        "gross_position_notional": round(gross, 2),
        "gross_exposure_multiple": (
            round(gross / eq, 4) if eq > 1e-9 else None
        ),
        "policy": {
            "max_gross_exposure_multiple": rules.max_gross_exposure_multiple,
            "max_order_notional": rules.max_order_notional,
            "max_shares_per_symbol": rules.max_shares_per_symbol,
            "slippage_bps": rules.slippage_bps,
            "slippage_impact_bps_per_million": (
                rules.slippage_impact_bps_per_million
            ),
            "max_portfolio_var_95_pct_of_equity": (
                rules.max_portfolio_var_95_pct_of_equity
            ),
            "max_portfolio_cvar_95_pct_of_equity": (
                rules.max_portfolio_cvar_95_pct_of_equity
            ),
        },
        "budget": build_risk_budget_section(conn, rules),
        "position_count": len(ps.positions),
    }


def stress_book_pnl_impact(
    ledger: Any, shocks: dict[str, float],
) -> dict[str, Any]:
    """
    Linear P&L shock: each symbol moves by fraction (e.g. -0.1 => -10% on mark).
    """
    d = 0.0
    ps = ledger.portfolio_state()
    for sym, pos in ps.positions.items():
        pct = float(shocks.get(sym, shocks.get(sym.upper(), 0.0)))
        d += pos.quantity * pos.mark_price * pct
    eq = ledger.estimated_equity()
    return {
        "delta_equity_approx": round(d, 2),
        "hypothetical_equity_approx": round(eq + d, 2),
        "current_equity": round(eq, 2),
        "symbols_stressed": sorted(shocks.keys()),
    }
