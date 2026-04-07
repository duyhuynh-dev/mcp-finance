"""VaR/CVaR budget metrics and pre-trade rejections."""

from __future__ import annotations

import tempfile
from pathlib import Path

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.risk_budget import (
    MIN_RETURNS_FOR_BUDGET,
    check_var_cvar_budget,
    equity_returns_from_equities,
    var_cvar_95_pct_from_returns,
)
from finance_core.types import OrderSide, Position, RejectionReason


def test_equity_returns_and_var_cvar() -> None:
    eq = [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0, 55.0, 50.0]
    r = equity_returns_from_equities(eq)
    assert len(r) == 10
    v, c = var_cvar_95_pct_from_returns(r)
    assert v > 0 and c > 0


def test_var_cvar_short_history_returns_zeros() -> None:
    r = [0.01, -0.02]
    v, c = var_cvar_95_pct_from_returns(r)
    assert v == 0.0 and c == 0.0


def test_pre_trade_rejects_when_var_exceeds_cap() -> None:
    rules = PolicyRules(
        version="rb",
        max_shares_per_symbol=10_000.0,
        max_order_notional=500_000.0,
        max_portfolio_var_95_pct_of_equity=0.04,
        max_portfolio_cvar_95_pct_of_equity=0.0,
    )
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "rb.db"
        lg = Ledger.open(
            str(db),
            quotes=MockQuoteProvider({"ZZZ": 100.0}),
            policy=PolicyEngine(rules),
        )
        lg.deposit(200_000.0, actor="t")
        lg.conn.execute("DELETE FROM equity_snapshots")
        e = 100_000.0
        for i in range(MIN_RETURNS_FOR_BUDGET + 5):
            lg.conn.execute(
                "INSERT INTO equity_snapshots (ts, equity) VALUES (?, ?)",
                (f"2024-01-{i+1:02d}T00:00:00+00:00", e),
            )
            e *= 0.95
        lg.conn.commit()

        r = lg.place_order("v1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
        assert not r.success
        assert r.rejection_reason == RejectionReason.MAX_VAR_BUDGET


def test_check_var_uses_gross_scale() -> None:
    rules = PolicyRules(
        version="rb2",
        max_shares_per_symbol=10_000.0,
        max_order_notional=500_000.0,
        max_portfolio_var_95_pct_of_equity=0.06,
        max_portfolio_cvar_95_pct_of_equity=0.0,
    )
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "rb2.db"
        lg = Ledger.open(
            str(db),
            quotes=MockQuoteProvider({"ZZZ": 100.0}),
            policy=PolicyEngine(rules),
        )
        lg.conn.execute("DELETE FROM equity_snapshots")
        e = 100_000.0
        for i in range(MIN_RETURNS_FOR_BUDGET + 5):
            lg.conn.execute(
                "INSERT INTO equity_snapshots (ts, equity) VALUES (?, ?)",
                (f"2024-01-{i+1:02d}T00:00:00+00:00", e),
            )
            e *= 0.95
        lg.conn.commit()

        positions = {
            "ZZZ": Position(
                symbol="ZZZ",
                quantity=100.0,
                avg_cost=100.0,
                mark_price=100.0,
                market_value=10_000.0,
                unrealized_pnl=0.0,
            ),
        }
        # Doubling gross should push scaled VaR over 0.06 if raw VaR ~ 0.05
        reason = check_var_cvar_budget(
            lg.conn,
            rules,
            positions,
            "ZZZ",
            OrderSide.BUY,
            100.0,
            100.0,
        )
        assert reason == RejectionReason.MAX_VAR_BUDGET
