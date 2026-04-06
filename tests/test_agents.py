"""Tests for multi-agent orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from finance_core.agents import AgentManager
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide


def _setup():
    td = tempfile.mkdtemp()
    db = str(Path(td) / "t.db")
    quotes = MockQuoteProvider({"AAPL": 180.0, "MSFT": 380.0})
    lg = Ledger.open(db, quotes=quotes, policy=PolicyEngine(PolicyRules.default()))
    lg.deposit(100_000.0, actor="t")
    mgr = AgentManager(lg.conn)
    return lg, mgr


def test_register_and_list():
    _, mgr = _setup()
    a = mgr.register("alpha", 50_000.0)
    assert a.name == "alpha"
    assert a.budget == 50_000.0
    agents = mgr.list_all()
    assert len(agents) == 1
    assert agents[0].name == "alpha"


def test_agent_get_by_name():
    _, mgr = _setup()
    mgr.register("beta", 10_000.0, allowed_symbols=["AAPL"])
    a = mgr.get_by_name("beta")
    assert a is not None
    assert a.allowed_symbols == ["AAPL"]


def test_symbol_check():
    _, mgr = _setup()
    a = mgr.register("gamma", 10_000.0, allowed_symbols=["AAPL"])
    assert mgr.check_symbol_allowed(a.id, "AAPL")
    assert not mgr.check_symbol_allowed(a.id, "MSFT")


def test_budget_check():
    lg, mgr = _setup()
    a = mgr.register("delta", 5_000.0)
    assert mgr.check_budget(a.id, 3_000.0)
    lg.place_order("d1", "AAPL", OrderSide.BUY, 20.0, actor="t", agent_id=a.id)
    assert not mgr.check_budget(a.id, 5_000.0)


def test_agent_stats():
    lg, mgr = _setup()
    a = mgr.register("stats-agent", 100_000.0)
    lg.place_order("sa1", "AAPL", OrderSide.BUY, 5.0, actor="t", agent_id=a.id)
    lg.place_order("sa2", "MSFT", OrderSide.BUY, 2.0, actor="t", agent_id=a.id)
    stats = mgr.stats(a.id)
    assert stats is not None
    assert stats.total_orders == 2
    assert stats.filled_orders == 2
    assert stats.total_notional > 0
    assert "AAPL" in stats.positions
