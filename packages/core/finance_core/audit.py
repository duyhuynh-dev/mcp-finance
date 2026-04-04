from __future__ import annotations

import json
import sqlite3
from typing import Any

from finance_core.types import utc_now


def append_audit(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    payload: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> int:
    ts = utc_now().isoformat()
    cur = conn.execute(
        """
        INSERT INTO audit_events (ts, actor, action, payload_json, result_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ts,
            actor,
            action,
            json.dumps(payload, default=str),
            json.dumps(result, default=str) if result is not None else None,
        ),
    )
    return int(cur.lastrowid)


def list_audit(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, ts, actor, action, payload_json, result_json
        FROM audit_events
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "ts": r["ts"],
                "actor": r["actor"],
                "action": r["action"],
                "payload": json.loads(r["payload_json"]),
                "result": json.loads(r["result_json"]) if r["result_json"] else None,
            }
        )
    return out
