from __future__ import annotations

import tempfile
from pathlib import Path

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderKind, OrderSide, OrderStatus


def test_fee_on_market_buy() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.db"
        quotes = MockQuoteProvider({"ZZZ": 100.0})
        policy = PolicyEngine(
            PolicyRules(
                version="f",
                max_shares_per_symbol=1000.0,
                max_order_notional=50_000.0,
                fee_bps=100.0,
            )
        )
        lg = Ledger.open(str(db), quotes=quotes, policy=policy)
        lg.deposit(10_000.0, actor="t")
        r = lg.place_order("a", "ZZZ", OrderSide.BUY, 10.0, actor="t")
        assert r.success
        notional = 1000.0
        fee = round(notional * 100 / 10_000.0, 6)
        assert abs(lg.get_cash() - (10_000.0 - notional - fee)) < 1e-4


def test_limit_pending_and_cancel() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.db"
        quotes = MockQuoteProvider({"ZZZ": 200.0})
        policy = PolicyEngine(PolicyRules.default())
        lg = Ledger.open(str(db), quotes=quotes, policy=policy)
        lg.deposit(50_000.0, actor="t")
        r = lg.place_order(
            "lim1",
            "ZZZ",
            OrderSide.BUY,
            1.0,
            order_kind=OrderKind.LIMIT,
            limit_price=150.0,
            actor="t",
        )
        assert r.status == OrderStatus.PENDING
        oid = r.order_id
        assert oid is not None
        c = lg.cancel_order(oid, actor="t")
        assert c["ok"] is True
