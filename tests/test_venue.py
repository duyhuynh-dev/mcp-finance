from __future__ import annotations

import sqlite3

from finance_core.causal import list_causal_events
from finance_core.db import init_schema
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.types import OrderKind, OrderSide
from finance_core.venue import SimulatedExecutionVenue, VenueConfig, VenueOrderStatus


def _venue(depth: float = 5.0) -> SimulatedExecutionVenue:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    lg = Ledger(conn, quotes=MockQuoteProvider({"AAPL": 100.0}))
    lg.deposit(25_000, actor="test")
    return SimulatedExecutionVenue(
        lg,
        VenueConfig(
            base_spread_bps=10,
            impact_bps_per_1000_shares=5,
            depth_per_tick=depth,
            latency_ticks=1,
            default_tif_ticks=4,
        ),
    )


def test_venue_market_order_lifecycle_partial_then_filled():
    venue = _venue(depth=5)
    first = venue.submit_order(
        client_order_id="venue-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=12,
        order_type=OrderKind.MARKET,
    )
    assert first["status"] in (VenueOrderStatus.OPEN.value, VenueOrderStatus.PARTIAL.value)
    venue.tick()
    venue.tick()
    final = venue.get_order(first["id"])
    assert final is not None
    assert final["status"] == VenueOrderStatus.FILLED.value
    assert final["filled_quantity"] == 12
    assert len(final["fills"]) == 3
    events = list_causal_events(venue.conn, limit=50)
    assert any(e["event_type"] == "venue.fill" for e in events)


def test_venue_limit_order_rests_and_expires():
    venue = _venue(depth=10)
    order = venue.submit_order(
        client_order_id="venue-limit",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderKind.LIMIT,
        limit_price=90,
    )
    assert order["status"] == VenueOrderStatus.OPEN.value
    for _ in range(5):
        order = venue.tick_order(order["id"])
    assert order["status"] == VenueOrderStatus.EXPIRED.value


def test_venue_cancel_open_order():
    venue = _venue(depth=10)
    order = venue.submit_order(
        client_order_id="venue-cancel",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderKind.LIMIT,
        limit_price=90,
    )
    res = venue.cancel_order(order["id"])
    assert res["ok"] is True
    assert res["order"]["status"] == VenueOrderStatus.CANCELLED.value
