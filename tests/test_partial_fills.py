"""Tests for partial fill / order book simulation."""

from __future__ import annotations

import sqlite3

from finance_core.db import init_schema
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.orderbook import LiquidityConfig, compute_fill_quantity
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide, OrderStatus


def _ledger() -> Ledger:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    lg = Ledger(conn, quotes=MockQuoteProvider())
    lg.set_policy(PolicyEngine(PolicyRules.default()))
    lg.deposit(500_000)
    return lg


def test_compute_fill_no_liquidity() -> None:
    assert compute_fill_quantity(100.0, None, "AAPL") == 100.0


def test_compute_fill_with_liquidity() -> None:
    liq = LiquidityConfig(base_depth=50, depth_variance=0.0, seed=42)
    assert compute_fill_quantity(100.0, liq, "AAPL") == 50.0


def test_full_fill_without_liquidity() -> None:
    lg = _ledger()
    r = lg.place_order("full-1", "AAPL", OrderSide.BUY, 10)
    assert r.status == OrderStatus.FILLED
    assert r.filled_quantity == 10.0
    assert r.remaining_quantity == 0.0


def test_partial_fill_with_liquidity() -> None:
    lg = _ledger()
    liq = LiquidityConfig(base_depth=5, depth_variance=0.0, seed=42)
    r = lg.place_order(
        "partial-1", "AAPL", OrderSide.BUY, 20,
        liquidity=liq,
    )
    assert r.status == OrderStatus.PARTIAL
    assert r.filled_quantity == 5.0
    assert r.remaining_quantity == 15.0
    assert r.fill_price is not None

    pos = lg.position_quantity("AAPL")
    assert abs(pos - 5.0) < 1e-9


def test_sweep_completes_partial() -> None:
    lg = _ledger()
    liq = LiquidityConfig(base_depth=5, depth_variance=0.0, seed=42)
    r = lg.place_order(
        "sweep-1", "AAPL", OrderSide.BUY, 10,
        liquidity=liq,
    )
    assert r.status == OrderStatus.PARTIAL

    sweep_liq = LiquidityConfig(base_depth=100, depth_variance=0.0, seed=42)
    sweeps = lg.sweep_partial_orders(sweep_liq)
    assert len(sweeps) == 1
    assert sweeps[0]["status"] == "FILLED"

    pos = lg.position_quantity("AAPL")
    assert abs(pos - 10.0) < 1e-9


def test_cancel_partial_order() -> None:
    lg = _ledger()
    liq = LiquidityConfig(base_depth=3, depth_variance=0.0, seed=42)
    r = lg.place_order(
        "cancel-p", "AAPL", OrderSide.BUY, 10,
        liquidity=liq,
    )
    assert r.status == OrderStatus.PARTIAL
    oid = r.order_id
    assert oid is not None

    cancel_result = lg.cancel_order(oid)
    assert cancel_result["ok"] is True

    pos = lg.position_quantity("AAPL")
    assert abs(pos - 3.0) < 1e-9


def test_partial_sell() -> None:
    lg = _ledger()
    lg.place_order("buy-ps", "AAPL", OrderSide.BUY, 20)

    liq = LiquidityConfig(base_depth=8, depth_variance=0.0, seed=42)
    r = lg.place_order(
        "sell-ps", "AAPL", OrderSide.SELL, 15,
        liquidity=liq,
    )
    assert r.status == OrderStatus.PARTIAL
    assert r.filled_quantity == 8.0
    assert r.remaining_quantity == 7.0
