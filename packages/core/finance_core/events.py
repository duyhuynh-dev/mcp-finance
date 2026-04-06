"""Event sourcing: typed event definitions + state reconstruction from audit log."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from finance_core.types import OrderSide


@dataclass
class ReplayState:
    """Reconstructed portfolio state at a given event_id."""

    event_id: int
    timestamp: str
    cash: float
    positions: dict[str, float]
    total_deposits: float
    total_orders: int
    total_fills: int
    realized_pnl: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "cash": round(self.cash, 2),
            "positions": {k: round(v, 6) for k, v in self.positions.items()},
            "total_deposits": round(self.total_deposits, 2),
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
            "realized_pnl": round(self.realized_pnl, 2),
        }


def replay_to_event(conn: sqlite3.Connection, event_id: int) -> ReplayState:
    """Reconstruct portfolio state by replaying events up to event_id."""
    events = conn.execute(
        """
        SELECT id, ts, action, payload_json, result_json
        FROM audit_events
        WHERE id <= ?
        ORDER BY id ASC
        """,
        (event_id,),
    ).fetchall()

    cash = 0.0
    positions: dict[str, float] = {}
    total_deposits = 0.0
    total_orders = 0
    total_fills = 0
    realized_pnl = 0.0
    last_ts = ""

    for ev in events:
        action = ev["action"]
        payload = json.loads(ev["payload_json"]) if ev["payload_json"] else {}
        result = json.loads(ev["result_json"]) if ev["result_json"] else {}
        last_ts = ev["ts"]

        if action == "deposit":
            amount = float(payload.get("amount", 0))
            cash += amount
            total_deposits += amount

        elif action == "place_order":
            total_orders += 1
            if result.get("success") and result.get("status") == "FILLED":
                total_fills += 1
                fill_price = result.get("fill_price", 0)
                symbol = payload.get("symbol", "")
                side = payload.get("side", "")
                quantity = float(payload.get("quantity", 0))
                notional = quantity * fill_price if fill_price else 0

                if side == OrderSide.BUY.value:
                    cash -= notional
                    positions[symbol] = positions.get(symbol, 0) + quantity
                elif side == OrderSide.SELL.value:
                    cash += notional
                    positions[symbol] = positions.get(symbol, 0) - quantity

        elif action == "fill_limit_order":
            total_fills += 1
            rpnl = float(result.get("realized_pnl", 0))
            realized_pnl += rpnl

        elif action == "cancel_order":
            pass

    positions = {k: v for k, v in positions.items() if abs(v) > 1e-9}

    fills_up_to = conn.execute(
        """
        SELECT COALESCE(SUM(realized_pnl), 0) AS rpnl FROM fills
        WHERE id <= (SELECT COALESCE(MAX(f.id), 0) FROM fills f
                     JOIN orders o ON f.order_id = o.id
                     WHERE o.created_at <= (SELECT ts FROM audit_events WHERE id = ?))
        """,
        (event_id,),
    ).fetchone()
    if fills_up_to:
        realized_pnl = float(fills_up_to["rpnl"])

    return ReplayState(
        event_id=event_id,
        timestamp=last_ts,
        cash=cash,
        positions=positions,
        total_deposits=total_deposits,
        total_orders=total_orders,
        total_fills=total_fills,
        realized_pnl=realized_pnl,
    )


def max_event_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(id), 0) AS m FROM audit_events"
    ).fetchone()
    return int(row["m"]) if row else 0


def event_timeline(
    conn: sqlite3.Connection, limit: int = 100
) -> list[dict[str, Any]]:
    """Return event IDs and timestamps for the time-travel slider."""
    rows = conn.execute(
        """
        SELECT id, ts, action FROM audit_events
        ORDER BY id ASC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {"id": int(r["id"]), "ts": r["ts"], "action": r["action"]}
        for r in rows
    ]
