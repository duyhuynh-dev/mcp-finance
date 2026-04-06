"""Tests for the risk analytics module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.risk import compute_risk_metrics
from finance_core.types import OrderSide


def _make_ledger(prices: dict[str, float] | None = None) -> Ledger:
    td = tempfile.mkdtemp()
    db = str(Path(td) / "t.db")
    quotes = MockQuoteProvider(prices or {"ZZZ": 100.0})
    return Ledger.open(db, quotes=quotes, policy=PolicyEngine(PolicyRules.default()))


def test_risk_empty():
    lg = _make_ledger()
    m = compute_risk_metrics(lg.conn)
    assert m.sharpe_ratio == 0.0
    assert m.total_trades == 0


def test_risk_after_trades():
    lg = _make_ledger({"ZZZ": 100.0})
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    lg._quotes.set_price("ZZZ", 110.0)
    lg.place_order("s1", "ZZZ", OrderSide.SELL, 10.0, actor="t")

    m = compute_risk_metrics(lg.conn)
    assert m.total_trades >= 1
    assert m.win_rate > 0
    assert len(m.equity_curve) >= 2
    assert m.total_return_pct != 0


def test_risk_drawdown():
    lg = _make_ledger({"ZZZ": 100.0})
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    lg._quotes.set_price("ZZZ", 80.0)
    lg.place_order("s1", "ZZZ", OrderSide.SELL, 10.0, actor="t")

    m = compute_risk_metrics(lg.conn)
    assert m.max_drawdown > 0
    assert len(m.drawdown_curve) > 0


def test_risk_to_dict():
    lg = _make_ledger({"ZZZ": 100.0})
    lg.deposit(10_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 5.0, actor="t")
    m = compute_risk_metrics(lg.conn)
    d = m.to_dict()
    assert "sharpe_ratio" in d
    assert "var_95" in d
    assert "correlation_matrix" in d
