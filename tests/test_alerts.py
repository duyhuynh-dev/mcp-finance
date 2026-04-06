"""Tests for alert engine."""

from __future__ import annotations

import sqlite3

from finance_core.alerts import AlertEngine, AlertType
from finance_core.db import init_schema


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_create_and_list_rules() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    r = engine.create_rule("dd_alert", AlertType.DRAWDOWN_ABOVE, 0.1)
    assert r.name == "dd_alert"
    assert r.alert_type == AlertType.DRAWDOWN_ABOVE

    rules = engine.list_rules()
    assert len(rules) == 1
    assert rules[0].threshold == 0.1


def test_delete_rule() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    r = engine.create_rule("temp", AlertType.PNL_BELOW, -1000)
    engine.delete_rule(r.id)
    assert len(engine.list_rules()) == 0


def test_evaluate_drawdown_fires() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    engine.create_rule("dd_high", AlertType.DRAWDOWN_ABOVE, 0.05)

    fired = engine.evaluate(
        equity=95_000,
        cash=95_000,
        positions={},
        realized_pnl=0,
        max_drawdown_pct=0.08,
    )
    assert len(fired) == 1
    assert "drawdown" in fired[0].message.lower()
    assert fired[0].severity == "critical"


def test_evaluate_pnl_fires() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    engine.create_rule("pnl_low", AlertType.PNL_BELOW, -500)

    fired = engine.evaluate(
        equity=90_000, cash=90_000, positions={},
        realized_pnl=-800, max_drawdown_pct=0.01,
    )
    assert len(fired) == 1
    assert "P&L" in fired[0].message


def test_evaluate_equity_below() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    engine.create_rule("eq_low", AlertType.EQUITY_BELOW, 50_000)

    fired = engine.evaluate(
        equity=45_000, cash=45_000, positions={},
        realized_pnl=0, max_drawdown_pct=0.0,
    )
    assert len(fired) == 1


def test_evaluate_no_fire() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    engine.create_rule("dd_safe", AlertType.DRAWDOWN_ABOVE, 0.5)

    fired = engine.evaluate(
        equity=100_000, cash=100_000, positions={},
        realized_pnl=500, max_drawdown_pct=0.01,
    )
    assert len(fired) == 0


def test_notifications_persisted() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    engine.create_rule("test_notif", AlertType.EQUITY_BELOW, 100_000)

    engine.evaluate(
        equity=50_000, cash=50_000, positions={},
        realized_pnl=0, max_drawdown_pct=0.0,
    )

    notifs = engine.list_notifications()
    assert len(notifs) == 1
    assert notifs[0].alert_name == "test_notif"


def test_rule_to_dict() -> None:
    conn = _db()
    engine = AlertEngine(conn)
    r = engine.create_rule("dict_test", AlertType.EQUITY_ABOVE, 200_000)
    d = r.to_dict()
    assert d["name"] == "dict_test"
    assert d["alert_type"] == "equity_above"
    assert d["threshold"] == 200_000
