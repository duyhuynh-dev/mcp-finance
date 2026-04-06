"""Tests for event sourcing and replay."""

from __future__ import annotations

import tempfile
from pathlib import Path

from finance_core.events import event_timeline, max_event_id, replay_to_event
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide


def _make_ledger():
    td = tempfile.mkdtemp()
    db = str(Path(td) / "t.db")
    quotes = MockQuoteProvider({"ZZZ": 100.0})
    return Ledger.open(db, quotes=quotes, policy=PolicyEngine(PolicyRules.default()))


def test_replay_empty():
    lg = _make_ledger()
    mid = max_event_id(lg.conn)
    assert mid == 0


def test_replay_after_deposit():
    lg = _make_ledger()
    lg.deposit(10_000.0, actor="t")
    mid = max_event_id(lg.conn)
    assert mid >= 1
    state = replay_to_event(lg.conn, mid)
    assert state.cash == 10_000.0
    assert state.total_deposits == 10_000.0


def test_replay_partial():
    lg = _make_ledger()
    lg.deposit(5_000.0, actor="t")
    mid1 = max_event_id(lg.conn)
    lg.deposit(3_000.0, actor="t")
    mid2 = max_event_id(lg.conn)

    s1 = replay_to_event(lg.conn, mid1)
    s2 = replay_to_event(lg.conn, mid2)
    assert s1.cash == 5_000.0
    assert s2.cash == 8_000.0


def test_event_timeline_returns_events():
    lg = _make_ledger()
    lg.deposit(1_000.0, actor="t")
    lg.place_order("x1", "ZZZ", OrderSide.BUY, 1.0, actor="t")
    tl = event_timeline(lg.conn)
    assert len(tl) >= 2
    assert tl[0]["action"] == "deposit"


def test_replay_with_order():
    lg = _make_ledger()
    lg.deposit(50_000.0, actor="t")
    lg.place_order("b1", "ZZZ", OrderSide.BUY, 10.0, actor="t")
    mid = max_event_id(lg.conn)
    state = replay_to_event(lg.conn, mid)
    assert state.total_orders >= 1
    assert state.total_fills >= 1
