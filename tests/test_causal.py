from __future__ import annotations

import sqlite3

from finance_core.agent_actions import evaluate_trade_decision, record_agent_action
from finance_core.causal import (
    counterfactual_policy_replay,
    get_causal_chain,
    list_causal_events,
    replay_causal_summary,
    verify_causal_integrity,
)
from finance_core.db import init_schema
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide


def _ledger() -> Ledger:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    lg = Ledger(conn, quotes=MockQuoteProvider({"AAPL": 100.0}))
    lg.set_policy(
        PolicyEngine(
            PolicyRules(
                version="t",
                max_shares_per_symbol=1000,
                max_order_notional=100_000,
            )
        )
    )
    return lg


def test_causal_log_integrity_and_chain_from_order_flow():
    lg = _ledger()
    lg.deposit(10_000, actor="test")
    lg.place_order("causal-order-1", "AAPL", OrderSide.BUY, 5, actor="test")
    events = list_causal_events(lg.conn, limit=20)
    assert events
    assert any(e["event_type"] == "audit.deposit" for e in events)
    assert any(e["event_type"] == "execution.order_filled" for e in events)
    assert verify_causal_integrity(lg.conn)["ok"] is True

    filled = next(e for e in events if e["event_type"] == "execution.order_filled")
    chain = get_causal_chain(lg.conn, filled["id"])
    assert chain is not None
    assert chain["correlation_id"] == "client_order_id:causal-order-1"
    assert chain["graph"]["nodes"]


def test_causal_counterfactual_changes_agent_decision():
    lg = _ledger()
    lg.deposit(10_000, actor="test")
    decision = evaluate_trade_decision(
        lg, symbol="AAPL", side="BUY", quantity=10, actor="test", agent_id=None,
    )
    decision["agent"] = {"id": 7, "name": "agent-seven"}
    record_agent_action(
        lg.conn,
        actor="test",
        tool="place_order",
        action="order_placed",
        decision=decision,
        result={"ok": True},
    )
    replay = replay_causal_summary(lg.conn)
    assert replay["agent_decisions"]["ALLOW"] == 1
    cf = counterfactual_policy_replay(
        lg.conn, max_order_notional=100, require_approval_for_all_agents=True,
    )
    assert cf["changed_decisions"] == 1
    assert cf["changes"][0]["counterfactual_decision"] == "REJECT"
