"""Canonical causal event log, forensic chains, and counterfactual policy replay."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from finance_core.types import utc_now


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str, sort_keys=True)


def _state_hash(
    *,
    event_type: str,
    actor: str,
    agent_id: int | None,
    correlation_id: str,
    causation_id: int | None,
    payload: dict[str, Any],
    previous_hash: str,
) -> str:
    raw = _json(
        {
            "previous_hash": previous_hash,
            "event_type": event_type,
            "actor": actor,
            "agent_id": agent_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "payload": payload,
        }
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def infer_correlation_id(payload: dict[str, Any], fallback: str) -> str:
    for key in (
        "correlation_id",
        "request_id",
        "client_order_id",
        "intent_id",
        "order_id",
        "research_run_id",
        "id",
    ):
        val = payload.get(key)
        if val is not None and val != "":
            return f"{key}:{val}"
    requested = payload.get("requested_order")
    if isinstance(requested, dict) and requested.get("symbol"):
        sym = requested.get("symbol")
        side = requested.get("side")
        qty = requested.get("quantity")
        return f"proposal:{sym}:{side}:{qty}"
    return fallback


def append_causal_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    agent_id: int | None = None,
    correlation_id: str | None = None,
    causation_id: int | None = None,
    source_table: str | None = None,
    source_id: int | None = None,
) -> int:
    row = conn.execute(
        "SELECT id, state_hash FROM causal_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    previous_hash = str(row["state_hash"]) if row else "genesis"
    corr = correlation_id or infer_correlation_id(payload, f"event:{event_type}")
    h = _state_hash(
        event_type=event_type,
        actor=actor,
        agent_id=agent_id,
        correlation_id=corr,
        causation_id=causation_id,
        payload=payload,
        previous_hash=previous_hash,
    )
    cur = conn.execute(
        """
        INSERT INTO causal_events (
            ts, event_type, actor, agent_id, correlation_id, causation_id,
            source_table, source_id, payload_json, state_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            utc_now().isoformat(),
            event_type,
            actor,
            agent_id,
            corr,
            causation_id,
            source_table,
            source_id,
            _json(payload),
            h,
        ),
    )
    return int(cur.lastrowid)


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "ts": row["ts"],
        "event_type": row["event_type"],
        "actor": row["actor"],
        "agent_id": int(row["agent_id"]) if row["agent_id"] is not None else None,
        "correlation_id": row["correlation_id"],
        "causation_id": (
            int(row["causation_id"]) if row["causation_id"] is not None else None
        ),
        "source_table": row["source_table"],
        "source_id": int(row["source_id"]) if row["source_id"] is not None else None,
        "payload": json.loads(row["payload_json"] or "{}"),
        "state_hash": row["state_hash"],
    }


def list_causal_events(
    conn: sqlite3.Connection, *, limit: int = 100, offset: int = 0,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM causal_events
        ORDER BY id DESC LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [_row_to_event(r) for r in rows]


def get_causal_chain(conn: sqlite3.Connection, event_id: int) -> dict[str, Any] | None:
    root = conn.execute(
        "SELECT * FROM causal_events WHERE id = ?", (event_id,),
    ).fetchone()
    if root is None:
        return None
    corr = root["correlation_id"]
    rows = conn.execute(
        """
        SELECT * FROM causal_events
        WHERE correlation_id = ?
        ORDER BY id ASC
        """,
        (corr,),
    ).fetchall()
    events = [_row_to_event(r) for r in rows]
    nodes = [
        {
            "id": e["id"],
            "label": e["event_type"],
            "actor": e["actor"],
            "agent_id": e["agent_id"],
            "state_hash": e["state_hash"][:12],
        }
        for e in events
    ]
    ids = {e["id"] for e in events}
    edges = []
    previous: int | None = None
    for e in events:
        if e["causation_id"] in ids:
            edges.append({"from": e["causation_id"], "to": e["id"], "type": "caused"})
        elif previous is not None:
            edges.append({"from": previous, "to": e["id"], "type": "sequence"})
        previous = e["id"]
    return {
        "root_event_id": int(root["id"]),
        "correlation_id": corr,
        "events": events,
        "graph": {"nodes": nodes, "edges": edges},
        "integrity": verify_causal_integrity(conn, to_event_id=int(root["id"])),
    }


def verify_causal_integrity(
    conn: sqlite3.Connection, *, to_event_id: int | None = None,
) -> dict[str, Any]:
    where = "WHERE id <= ?" if to_event_id is not None else ""
    params: tuple[Any, ...] = (to_event_id,) if to_event_id is not None else ()
    rows = conn.execute(
        f"SELECT * FROM causal_events {where} ORDER BY id ASC", params,
    ).fetchall()
    previous = "genesis"
    checked = 0
    for r in rows:
        payload = json.loads(r["payload_json"] or "{}")
        expected = _state_hash(
            event_type=r["event_type"],
            actor=r["actor"],
            agent_id=int(r["agent_id"]) if r["agent_id"] is not None else None,
            correlation_id=r["correlation_id"],
            causation_id=(
                int(r["causation_id"]) if r["causation_id"] is not None else None
            ),
            payload=payload,
            previous_hash=previous,
        )
        if expected != r["state_hash"]:
            return {
                "ok": False,
                "checked_events": checked,
                "failed_event_id": int(r["id"]),
                "expected": expected,
                "actual": r["state_hash"],
            }
        previous = r["state_hash"]
        checked += 1
    return {"ok": True, "checked_events": checked, "head_hash": previous}


def replay_causal_summary(
    conn: sqlite3.Connection, *, to_event_id: int | None = None,
) -> dict[str, Any]:
    where = "WHERE id <= ?" if to_event_id is not None else ""
    params: tuple[Any, ...] = (to_event_id,) if to_event_id is not None else ()
    rows = conn.execute(
        f"SELECT event_type, payload_json FROM causal_events {where} ORDER BY id ASC",
        params,
    ).fetchall()
    counts: dict[str, int] = {}
    agent_decisions = {"ALLOW": 0, "REJECT": 0, "RESIZE": 0, "REQUIRE_APPROVAL": 0}
    correlations: set[str] = set()
    for r in rows:
        event_type = str(r["event_type"])
        counts[event_type] = counts.get(event_type, 0) + 1
        payload = json.loads(r["payload_json"] or "{}")
        corr = infer_correlation_id(payload, "")
        if corr:
            correlations.add(corr)
        decision = payload.get("decision")
        if isinstance(decision, dict):
            d = str(decision.get("decision", ""))
            if d in agent_decisions:
                agent_decisions[d] += 1
        elif str(decision) in agent_decisions:
            agent_decisions[str(decision)] += 1
    return {
        "to_event_id": to_event_id,
        "total_events": len(rows),
        "event_counts": counts,
        "agent_decisions": agent_decisions,
        "correlation_count": len(correlations),
        "integrity": verify_causal_integrity(conn, to_event_id=to_event_id),
    }


def counterfactual_policy_replay(
    conn: sqlite3.Connection,
    *,
    max_order_notional: float | None = None,
    max_gross_exposure_multiple: float | None = None,
    require_approval_for_all_agents: bool = False,
    limit: int = 200,
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT * FROM causal_events
        WHERE event_type LIKE 'agent.%'
        ORDER BY id ASC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    changes = []
    for r in rows:
        payload = json.loads(r["payload_json"] or "{}")
        decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else payload
        if not isinstance(decision, dict):
            continue
        original = str(decision.get("decision", "UNKNOWN"))
        would = original
        reasons: list[str] = []
        notional = float(decision.get("projected_notional") or 0.0)
        gross_multiple = decision.get("projected_gross_multiple_after")
        if max_order_notional is not None and notional > max_order_notional:
            would = "REJECT"
            reasons.append("COUNTERFACTUAL_MAX_ORDER_NOTIONAL")
        if (
            max_gross_exposure_multiple is not None
            and gross_multiple is not None
            and float(gross_multiple) > max_gross_exposure_multiple
        ):
            would = "REJECT"
            reasons.append("COUNTERFACTUAL_GROSS_EXPOSURE")
        if (
            require_approval_for_all_agents
            and decision.get("agent") is not None
            and would in ("ALLOW", "RESIZE")
        ):
            would = "REQUIRE_APPROVAL"
            reasons.append("COUNTERFACTUAL_APPROVAL_REQUIRED")
        if would != original:
            changes.append(
                {
                    "event_id": int(r["id"]),
                    "ts": r["ts"],
                    "event_type": r["event_type"],
                    "correlation_id": r["correlation_id"],
                    "original_decision": original,
                    "counterfactual_decision": would,
                    "reasons": reasons,
                    "symbol": decision.get("symbol"),
                    "side": decision.get("side"),
                    "projected_notional": notional,
                    "projected_gross_multiple_after": gross_multiple,
                }
            )
    return {
        "policy": {
            "max_order_notional": max_order_notional,
            "max_gross_exposure_multiple": max_gross_exposure_multiple,
            "require_approval_for_all_agents": require_approval_for_all_agents,
        },
        "events_evaluated": len(rows),
        "changed_decisions": len(changes),
        "changes": changes,
    }
