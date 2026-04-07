"""Alerting system: threshold-based alerts with notification log."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from finance_core.db import transaction
from finance_core.types import utc_now


class AlertType(StrEnum):
    DRAWDOWN_ABOVE = "drawdown_above"
    PNL_BELOW = "pnl_below"
    CONCENTRATION_ABOVE = "concentration_above"
    EQUITY_BELOW = "equity_below"
    EQUITY_ABOVE = "equity_above"
    LOSS_STREAK = "loss_streak"
    RISK_BUDGET_USAGE_ABOVE = "risk_budget_usage_above"


@dataclass
class AlertRule:
    id: int
    name: str
    alert_type: AlertType
    threshold: float
    symbol: str | None
    is_active: bool
    created_at: str
    cooldown_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "alert_type": self.alert_type.value,
            "threshold": self.threshold,
            "symbol": self.symbol,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "cooldown_seconds": self.cooldown_seconds,
        }


@dataclass
class AlertNotification:
    id: int
    alert_id: int
    alert_name: str
    message: str
    severity: str
    fired_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "alert_name": self.alert_name,
            "message": self.message,
            "severity": self.severity,
            "fired_at": self.fired_at,
        }


class AlertEngine:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_rule(
        self,
        name: str,
        alert_type: AlertType,
        threshold: float,
        symbol: str | None = None,
        cooldown_seconds: int = 300,
    ) -> AlertRule:
        ts = utc_now().isoformat()
        with transaction(self._conn):
            cur = self._conn.execute(
                """INSERT INTO alert_rules
                   (name, alert_type, threshold, symbol, is_active, cooldown_seconds, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (name, alert_type.value, threshold, symbol, cooldown_seconds, ts),
            )
            return AlertRule(
                id=int(cur.lastrowid),
                name=name,
                alert_type=alert_type,
                threshold=threshold,
                symbol=symbol,
                is_active=True,
                created_at=ts,
                cooldown_seconds=cooldown_seconds,
            )

    def list_rules(self) -> list[AlertRule]:
        rows = self._conn.execute(
            "SELECT * FROM alert_rules ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_rule(r) for r in rows]

    def delete_rule(self, rule_id: int) -> bool:
        with transaction(self._conn):
            self._conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        return True

    def toggle_rule(self, rule_id: int, active: bool) -> bool:
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE alert_rules SET is_active = ? WHERE id = ?",
                (1 if active else 0, rule_id),
            )
        return True

    def list_notifications(self, limit: int = 50) -> list[AlertNotification]:
        rows = self._conn.execute(
            """SELECT n.id, n.alert_id, r.name AS alert_name,
                      n.message, n.severity, n.fired_at
               FROM alert_notifications n
               JOIN alert_rules r ON r.id = n.alert_id
               ORDER BY n.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            AlertNotification(
                id=int(r["id"]),
                alert_id=int(r["alert_id"]),
                alert_name=r["alert_name"],
                message=r["message"],
                severity=r["severity"],
                fired_at=r["fired_at"],
            )
            for r in rows
        ]

    def evaluate(
        self,
        equity: float,
        cash: float,
        positions: dict[str, float],
        realized_pnl: float,
        max_drawdown_pct: float,
        risk_budget_max_utilization: float | None = None,
    ) -> list[AlertNotification]:
        """Check all active rules against current portfolio state."""
        rules = self._conn.execute(
            "SELECT * FROM alert_rules WHERE is_active = 1"
        ).fetchall()

        total_value = equity
        fired: list[AlertNotification] = []

        for row in rules:
            rule = self._row_to_rule(row)
            if self._in_cooldown(rule.id, rule.cooldown_seconds):
                continue

            msg = self._check_rule(
                rule, equity, cash, positions, realized_pnl,
                max_drawdown_pct, total_value, risk_budget_max_utilization,
            )
            if msg:
                n = self._fire(rule, msg)
                fired.append(n)

        return fired

    def _check_rule(
        self,
        rule: AlertRule,
        equity: float,
        cash: float,
        positions: dict[str, float],
        realized_pnl: float,
        max_dd_pct: float,
        total_value: float,
        risk_budget_max_utilization: float | None = None,
    ) -> str | None:
        t = rule.threshold

        if rule.alert_type == AlertType.DRAWDOWN_ABOVE:
            if abs(max_dd_pct) > t:
                return f"Max drawdown {max_dd_pct:.2%} exceeds {t:.2%} threshold"

        elif rule.alert_type == AlertType.PNL_BELOW:
            if realized_pnl < t:
                return f"Realized P&L ${realized_pnl:,.2f} below ${t:,.2f} threshold"

        elif rule.alert_type == AlertType.CONCENTRATION_ABOVE:
            if total_value > 0 and rule.symbol:
                pos_val = positions.get(rule.symbol, 0.0)
                conc = abs(pos_val) / total_value
                if conc > t:
                    return (
                        f"{rule.symbol} concentration {conc:.1%}"
                        f" exceeds {t:.1%} threshold"
                    )

        elif rule.alert_type == AlertType.EQUITY_BELOW:
            if equity < t:
                return f"Equity ${equity:,.2f} below ${t:,.2f} threshold"

        elif rule.alert_type == AlertType.EQUITY_ABOVE:
            if equity > t:
                return f"Equity ${equity:,.2f} above ${t:,.2f} target"

        elif rule.alert_type == AlertType.LOSS_STREAK:
            streak = self._current_loss_streak()
            if streak >= int(t):
                return f"Loss streak of {streak} trades (threshold: {int(t)})"
        elif rule.alert_type == AlertType.RISK_BUDGET_USAGE_ABOVE:
            if (
                risk_budget_max_utilization is not None
                and risk_budget_max_utilization > t
            ):
                return (
                    "Risk budget utilization "
                    f"{risk_budget_max_utilization:.1%} exceeds {t:.1%} threshold"
                )

        return None

    def _current_loss_streak(self) -> int:
        rows = self._conn.execute(
            "SELECT realized_pnl FROM fills ORDER BY id DESC LIMIT 20"
        ).fetchall()
        streak = 0
        for r in rows:
            if float(r["realized_pnl"]) < 0:
                streak += 1
            else:
                break
        return streak

    def _in_cooldown(self, rule_id: int, cooldown_s: int) -> bool:
        row = self._conn.execute(
            """SELECT fired_at FROM alert_notifications
               WHERE alert_id = ? ORDER BY id DESC LIMIT 1""",
            (rule_id,),
        ).fetchone()
        if row is None:
            return False
        from datetime import datetime

        last = datetime.fromisoformat(
            row["fired_at"].replace("Z", "+00:00")
        )
        diff = (utc_now() - last).total_seconds()
        return diff < cooldown_s

    def _fire(self, rule: AlertRule, message: str) -> AlertNotification:
        severity = "warning"
        if rule.alert_type in (AlertType.DRAWDOWN_ABOVE, AlertType.LOSS_STREAK):
            severity = "critical"
        elif rule.alert_type == AlertType.EQUITY_ABOVE:
            severity = "info"

        ts = utc_now().isoformat()
        payload = json.dumps({"rule_id": rule.id, "message": message})

        with transaction(self._conn):
            cur = self._conn.execute(
                """INSERT INTO alert_notifications
                   (alert_id, message, severity, payload_json, fired_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (rule.id, message, severity, payload, ts),
            )

        from finance_core.broadcast import event_bus

        event_bus.publish({
            "type": "alert",
            "alert_id": rule.id,
            "name": rule.name,
            "severity": severity,
            "message": message,
        })

        return AlertNotification(
            id=int(cur.lastrowid),
            alert_id=rule.id,
            alert_name=rule.name,
            message=message,
            severity=severity,
            fired_at=ts,
        )

    @staticmethod
    def _row_to_rule(r: sqlite3.Row) -> AlertRule:
        return AlertRule(
            id=int(r["id"]),
            name=r["name"],
            alert_type=AlertType(r["alert_type"]),
            threshold=float(r["threshold"]),
            symbol=r["symbol"],
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            cooldown_seconds=int(r["cooldown_seconds"]),
        )
