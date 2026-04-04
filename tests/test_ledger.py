from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide, RejectionReason


@pytest.fixture
def ledger() -> Ledger:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.db"
        quotes = MockQuoteProvider({"ZZZ": 100.0})
        policy = PolicyEngine(
            PolicyRules(version="t", max_shares_per_symbol=500.0, max_order_notional=10_000.0)
        )
        lg = Ledger.open(str(db), quotes=quotes, policy=policy)
        lg.deposit(50_000.0, actor="test")
        yield lg


def test_buy_and_sell_round_trip(ledger: Ledger) -> None:
    r1 = ledger.place_order("c1", "ZZZ", OrderSide.BUY, 10.0, actor="test")
    assert r1.success
    assert r1.fill_price == 100.0
    assert ledger.get_cash() == 50_000.0 - 1_000.0
    assert ledger.position_quantity("ZZZ") == 10.0

    r2 = ledger.place_order("c2", "ZZZ", OrderSide.SELL, 10.0, actor="test")
    assert r2.success
    assert ledger.get_cash() == 50_000.0
    assert abs(ledger.position_quantity("ZZZ")) < 1e-6


def test_idempotent_client_order_id(ledger: Ledger) -> None:
    r1 = ledger.place_order("same", "ZZZ", OrderSide.BUY, 5.0, actor="test")
    r2 = ledger.place_order("same", "ZZZ", OrderSide.BUY, 5.0, actor="test")
    assert r1.order_id == r2.order_id
    assert ledger.get_cash() == 50_000.0 - 500.0


def test_insufficient_cash() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.db"
        quotes = MockQuoteProvider({"ZZZ": 100.0})
        policy = PolicyEngine(
            PolicyRules(version="t", max_shares_per_symbol=500.0, max_order_notional=10_000.0)
        )
        lg = Ledger.open(str(db), quotes=quotes, policy=policy)
        lg.deposit(5_000.0, actor="test")
        r = lg.place_order("big", "ZZZ", OrderSide.BUY, 60.0, actor="test")
        assert not r.success
        assert r.rejection_reason == RejectionReason.INSUFFICIENT_CASH


def test_policy_max_notional(ledger: Ledger) -> None:
    """Order notional 20_000 > 10_000 limit."""
    r = ledger.place_order("p1", "ZZZ", OrderSide.BUY, 200.0, actor="test")
    assert not r.success
    assert r.rejection_reason == RejectionReason.MAX_ORDER_NOTIONAL


def test_trading_disabled(ledger: Ledger) -> None:
    ledger.set_trading_enabled(False, actor="test")
    r = ledger.place_order("x", "ZZZ", OrderSide.BUY, 1.0, actor="test")
    assert not r.success
    assert r.rejection_reason == RejectionReason.TRADING_DISABLED
