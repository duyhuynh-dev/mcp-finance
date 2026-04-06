"""Tests for avg_cost, realized P&L, slippage, and new policy rules."""

from __future__ import annotations

import tempfile
from pathlib import Path

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide, RejectionReason


def _make_ledger(
    prices: dict[str, float] | None = None,
    rules: PolicyRules | None = None,
) -> Ledger:
    td = tempfile.mkdtemp()
    db = str(Path(td) / "t.db")
    quotes = MockQuoteProvider(prices or {"ZZZ": 100.0})
    policy = PolicyEngine(rules or PolicyRules.default())
    return Ledger.open(db, quotes=quotes, policy=policy)


def test_avg_cost_single_buy():
    lg = _make_ledger()
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    pos = lg._positions_map()["ZZZ"]
    assert abs(pos.avg_cost - 100.0) < 1e-4


def test_avg_cost_multiple_buys():
    lg = _make_ledger({"ZZZ": 100.0})
    lg.deposit(100_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    lg._quotes.set_price("ZZZ", 200.0)
    lg.place_order("b2", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    pos = lg._positions_map()["ZZZ"]
    assert abs(pos.avg_cost - 150.0) < 1e-4
    assert abs(pos.quantity - 20.0) < 1e-6


def test_realized_pnl_on_sell():
    lg = _make_ledger({"ZZZ": 100.0})
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    lg._quotes.set_price("ZZZ", 120.0)
    lg.place_order("s1", "ZZZ", OrderSide.SELL, 5.0, actor="t")
    fills = lg.list_fills(limit=10)
    sell_fill = [f for f in fills if f.side == OrderSide.SELL][0]
    assert sell_fill.realized_pnl > 0
    expected_rpnl = (120.0 - 100.0) * 5.0
    assert abs(sell_fill.realized_pnl - expected_rpnl) < 1e-2


def test_unrealized_pnl_in_portfolio():
    lg = _make_ledger({"ZZZ": 100.0})
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    lg._quotes.set_price("ZZZ", 110.0)
    state = lg.portfolio_state()
    pos = state.positions["ZZZ"]
    assert pos.mark_price == 110.0
    expected_upnl = (110.0 - 100.0) * 10.0
    assert abs(pos.unrealized_pnl - expected_upnl) < 1e-2
    assert abs(state.total_unrealized_pnl - expected_upnl) < 1e-2


def test_slippage_applied_to_buy():
    rules = PolicyRules(
        version="t",
        max_shares_per_symbol=1000.0,
        max_order_notional=50_000.0,
        slippage_bps=100.0,
    )
    lg = _make_ledger({"ZZZ": 100.0}, rules)
    lg.deposit(50_000.0, actor="t")
    r = lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    assert r.success
    expected_price = 100.0 * (1 + 100.0 / 10_000.0)
    assert r.fill_price is not None
    assert abs(r.fill_price - expected_price) < 1e-4


def test_slippage_applied_to_sell():
    rules = PolicyRules(
        version="t",
        max_shares_per_symbol=1000.0,
        max_order_notional=50_000.0,
        slippage_bps=100.0,
    )
    lg = _make_ledger({"ZZZ": 100.0}, rules)
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    r = lg.place_order("s1", "ZZZ", OrderSide.SELL, 10.0, actor="t")
    assert r.success
    expected_price = 100.0 * (1 - 100.0 / 10_000.0)
    assert r.fill_price is not None
    assert abs(r.fill_price - expected_price) < 1e-4


def test_max_daily_order_count():
    rules = PolicyRules(
        version="t",
        max_shares_per_symbol=1000.0,
        max_order_notional=50_000.0,
        max_daily_order_count=2,
    )
    lg = _make_ledger({"ZZZ": 10.0}, rules)
    lg.deposit(50_000.0, actor="t")
    r1 = lg.place_order("d1", "ZZZ", OrderSide.BUY, 1.0, actor="t")
    assert r1.success
    r2 = lg.place_order("d2", "ZZZ", OrderSide.BUY, 1.0, actor="t")
    assert r2.success
    r3 = lg.place_order("d3", "ZZZ", OrderSide.BUY, 1.0, actor="t")
    assert not r3.success
    assert r3.rejection_reason == RejectionReason.MAX_DAILY_ORDERS


def test_max_portfolio_concentration():
    rules = PolicyRules(
        version="t",
        max_shares_per_symbol=1000.0,
        max_order_notional=50_000.0,
        max_portfolio_concentration_pct=50.0,
    )
    lg = _make_ledger({"ZZZ": 100.0}, rules)
    lg.deposit(10_000.0, actor="t")
    r1 = lg.place_order("c1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    assert r1.success
    r2 = lg.place_order("c2", "ZZZ", OrderSide.BUY, 80.0, actor="t")
    assert not r2.success
    assert r2.rejection_reason == RejectionReason.MAX_CONCENTRATION


def test_equity_series_returns_latest():
    lg = _make_ledger()
    lg.deposit(1000.0, actor="t")
    for i in range(10):
        lg.deposit(100.0, actor="t")
    series = lg.equity_series(limit=5)
    assert len(series) == 5
    assert series[-1]["equity"] >= series[0]["equity"]
