"""Execution event log and replay helpers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from finance_core.types import utc_now


def append_execution_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    cur = conn.execute(
        """
        INSERT INTO execution_events (ts, event_type, payload_json)
        VALUES (?, ?, ?)
        """,
        (utc_now().isoformat(), event_type, json.dumps(payload, default=str)),
    )
    return int(cur.lastrowid)


def list_execution_events(
    conn: sqlite3.Connection,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, ts, event_type, payload_json
        FROM execution_events
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "ts": r["ts"],
            "event_type": r["event_type"],
            "payload": json.loads(r["payload_json"]),
        }
        for r in rows
    ]


def replay_summary(
    conn: sqlite3.Connection,
    *,
    to_event_id: int | None = None,
) -> dict[str, Any]:
    params: tuple[Any, ...] = ()
    where = ""
    if to_event_id is not None:
        where = "WHERE e.id <= ?"
        params = (int(to_event_id),)
    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_events,
          COALESCE(SUM(CASE WHEN e.event_type = 'order_rejected' THEN 1 ELSE 0 END), 0) AS rejects,
          COALESCE(SUM(CASE WHEN e.event_type = 'order_cancelled' THEN 1 ELSE 0 END), 0) AS cancels,
          COALESCE(SUM(CASE WHEN e.event_type = 'order_opened' THEN 1 ELSE 0 END), 0) AS opened,
          COALESCE(SUM(CASE WHEN e.event_type = 'order_filled' THEN 1 ELSE 0 END), 0) AS filled
        FROM execution_events e
        {where}
        """,
        params,
    ).fetchone()
    return {
        "to_event_id": to_event_id,
        "total_events": int(row["total_events"]) if row else 0,
        "orders_opened": int(row["opened"]) if row else 0,
        "orders_filled_or_partial": int(row["filled"]) if row else 0,
        "orders_rejected": int(row["rejects"]) if row else 0,
        "orders_cancelled": int(row["cancels"]) if row else 0,
    }
