"""Human-in-the-loop: pending order intents approved before ledger placement."""

from __future__ import annotations

import sqlite3
from enum import StrEnum
from typing import Any

from finance_core.db import transaction
from finance_core.types import OrderKind, OrderSide, utc_now


class OrderIntentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "client_order_id": row["client_order_id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "quantity": float(row["quantity"]),
        "order_kind": row["order_kind"],
        "limit_price": float(row["limit_price"]) if row["limit_price"] is not None else None,
        "agent_id": int(row["agent_id"]) if row["agent_id"] is not None else None,
        "actor": row["actor"],
        "status": row["status"],
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
    }


def create_order_intent(
    conn: sqlite3.Connection,
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    order_kind: str = "MARKET",
    limit_price: float | None = None,
    agent_id: int | None = None,
    actor: str = "api",
) -> dict[str, Any]:
    sym = symbol.strip().upper()
    sd = side.strip().upper()
    kind = order_kind.strip().upper()
    ts = utc_now().isoformat()
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO order_intents (
                    client_order_id, symbol, side, quantity,
                    order_kind, limit_price, agent_id, actor, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_order_id.strip(),
                    sym,
                    sd,
                    float(quantity),
                    kind,
                    float(limit_price) if limit_price is not None else None,
                    agent_id,
                    actor,
                    OrderIntentStatus.PENDING.value,
                    ts,
                ),
            )
    except sqlite3.IntegrityError:
        return {"error": "duplicate client_order_id"}
    row = conn.execute(
        "SELECT * FROM order_intents WHERE client_order_id = ?",
        (client_order_id.strip(),),
    ).fetchone()
    assert row is not None
    return _row_to_dict(row)


def approve_order_intent(ledger: Any, intent_id: int, *, actor: str) -> dict[str, Any]:
    row = ledger.conn.execute(
        "SELECT * FROM order_intents WHERE id = ?", (intent_id,),
    ).fetchone()
    if row is None:
        return {"error": "intent not found"}
    if row["status"] != OrderIntentStatus.PENDING.value:
        return {"error": "intent not pending", "status": row["status"]}

    side = OrderSide(row["side"])
    kind = OrderKind(row["order_kind"])
    lp = float(row["limit_price"]) if row["limit_price"] is not None else None
    aid = row["agent_id"]
    res = ledger.place_order(
        row["client_order_id"],
        row["symbol"],
        side,
        float(row["quantity"]),
        order_kind=kind,
        limit_price=lp,
        actor=actor,
        agent_id=int(aid) if aid is not None else None,
    )
    with transaction(ledger.conn):
        ledger.conn.execute(
            """
            UPDATE order_intents SET status = ?, resolved_at = ? WHERE id = ?
            """,
            (OrderIntentStatus.APPROVED.value, utc_now().isoformat(), intent_id),
        )
    return {"ok": True, "place_order": res.to_audit_dict()}


def reject_order_intent(conn: sqlite3.Connection, intent_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM order_intents WHERE id = ?", (intent_id,),
    ).fetchone()
    if row is None:
        return {"error": "intent not found"}
    if row["status"] != OrderIntentStatus.PENDING.value:
        return {"error": "intent not pending"}
    with transaction(conn):
        conn.execute(
            """
            UPDATE order_intents SET status = ?, resolved_at = ? WHERE id = ?
            """,
            (OrderIntentStatus.REJECTED.value, utc_now().isoformat(), intent_id),
        )
    return {"ok": True, "id": intent_id}


def list_pending_intents(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM order_intents
        WHERE status = ?
        ORDER BY id DESC LIMIT ?
        """,
        (OrderIntentStatus.PENDING.value, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
