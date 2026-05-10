"""Governed agent actions and explainable trade decisions."""

from __future__ import annotations

import json
import sqlite3
from enum import StrEnum
from typing import Any

from finance_core.agents import AgentManager
from finance_core.audit import append_audit
from finance_core.causal import append_causal_event, infer_correlation_id
from finance_core.db import transaction
from finance_core.pre_trade_risk import (
    clamp_quantity_for_gross_exposure,
    gross_notional,
    projected_gross_after_order,
)
from finance_core.risk_budget import build_risk_budget_section, check_var_cvar_budget
from finance_core.types import OrderKind, OrderSide, utc_now


class TradeDecision(StrEnum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    RESIZE = "RESIZE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


APPROVAL_NOTIONAL_FRACTION_OF_AGENT_LIMIT = 0.5


def _check(name: str, passed: bool, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail or {}}


def _reject(
    *,
    requested: dict[str, Any],
    actor: str,
    tool: str,
    agent: dict[str, Any] | None,
    reason: str,
    checks: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "decision": TradeDecision.REJECT.value,
        "allowed": False,
        "requires_approval": False,
        "reason": reason,
        "actor": actor,
        "tool": tool,
        "agent": agent,
        "requested_order": requested,
        "symbol": requested["symbol"],
        "side": requested["side"],
        "order_kind": requested["order_kind"],
        "requested_quantity": requested["quantity"],
        "adjusted_quantity": 0.0,
        "would_resize": False,
        "checks": checks,
    }
    if extra:
        out.update(extra)
    return out


def evaluate_trade_decision(
    ledger: Any,
    *,
    symbol: str,
    side: str | OrderSide,
    quantity: float,
    order_kind: str | OrderKind = OrderKind.MARKET,
    limit_price: float | None = None,
    actor: str = "api",
    agent_id: int | None = None,
    tool: str = "place_order",
) -> dict[str, Any]:
    """Return a stable, dashboard-facing explanation for a proposed order."""
    sym = symbol.strip().upper()
    sd = side if isinstance(side, OrderSide) else OrderSide(str(side).strip().upper())
    kind = (
        order_kind
        if isinstance(order_kind, OrderKind)
        else OrderKind(str(order_kind).strip().upper())
    )
    qty = float(quantity)
    requested = {
        "symbol": sym,
        "side": sd.value,
        "quantity": qty,
        "order_kind": kind.value,
        "limit_price": float(limit_price) if limit_price is not None else None,
    }
    checks: list[dict[str, Any]] = []

    if kind == OrderKind.LIMIT and (limit_price is None or limit_price <= 0):
        checks.append(_check("limit_price", False, {"limit_price": limit_price}))
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=None,
            reason="INVALID_LIMIT_PRICE",
            checks=checks,
        )
    checks.append(_check("limit_price", True))

    agent_payload: dict[str, Any] | None = None
    if agent_id is not None:
        mgr = AgentManager(ledger.conn)
        ag = mgr.get(int(agent_id))
        if ag is None:
            checks.append(_check("agent_exists", False, {"agent_id": agent_id}))
            return _reject(
                requested=requested,
                actor=actor,
                tool=tool,
                agent=None,
                reason="UNKNOWN_AGENT",
                checks=checks,
            )
        agent_payload = ag.to_dict()
        checks.append(_check("agent_exists", True, {"agent_id": ag.id, "name": ag.name}))
        checks.append(_check("agent_active", ag.is_active))
        if not ag.is_active:
            return _reject(
                requested=requested,
                actor=actor,
                tool=tool,
                agent=agent_payload,
                reason="AGENT_INACTIVE",
                checks=checks,
            )
        tool_allowed = ag.allowed_mcp_tools is None or tool in ag.allowed_mcp_tools
        checks.append(
            _check(
                "agent_tool_allowed",
                tool_allowed,
                {"tool": tool, "allowed_mcp_tools": ag.allowed_mcp_tools},
            )
        )
        if not tool_allowed:
            return _reject(
                requested=requested,
                actor=actor,
                tool=tool,
                agent=agent_payload,
                reason="AGENT_TOOL_NOT_ALLOWED",
                checks=checks,
            )
        symbol_allowed = mgr.check_symbol_allowed(ag.id, sym)
        checks.append(
            _check(
                "agent_symbol_allowed",
                symbol_allowed,
                {"symbol": sym, "allowed_symbols": ag.allowed_symbols},
            )
        )
        if not symbol_allowed:
            return _reject(
                requested=requested,
                actor=actor,
                tool=tool,
                agent=agent_payload,
                reason="AGENT_SYMBOL_NOT_ALLOWED",
                checks=checks,
            )

    if qty <= 0:
        checks.append(_check("quantity", False, {"quantity": qty}))
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason="INVALID_QUANTITY",
            checks=checks,
        )
    checks.append(_check("quantity", True, {"quantity": qty}))

    if not ledger.get_trading_enabled():
        checks.append(_check("trading_enabled", False))
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason="TRADING_DISABLED",
            checks=checks,
        )
    checks.append(_check("trading_enabled", True))

    try:
        quote = ledger.quotes.get_quote(sym)
        mark = float(quote.price)
    except ValueError:
        checks.append(_check("known_symbol", False, {"symbol": sym}))
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason="UNKNOWN_SYMBOL",
            checks=checks,
        )
    checks.append(_check("known_symbol", True, {"mark_price": mark}))

    policy_price = float(limit_price) if kind == OrderKind.LIMIT else mark
    notional_requested = qty * policy_price

    if agent_id is not None and agent_payload is not None:
        max_agent_notional = float(agent_payload["max_order_notional"])
        ok_agent_notional = notional_requested <= max_agent_notional + 1e-9
        checks.append(
            _check(
                "agent_max_order_notional",
                ok_agent_notional,
                {
                    "requested_notional": round(notional_requested, 2),
                    "max_order_notional": max_agent_notional,
                },
            )
        )
        if not ok_agent_notional:
            return _reject(
                requested=requested,
                actor=actor,
                tool=tool,
                agent=agent_payload,
                reason="AGENT_MAX_ORDER_NOTIONAL",
                checks=checks,
            )
        if sd == OrderSide.BUY:
            budget_ok = AgentManager(ledger.conn).check_budget(
                int(agent_id), notional_requested
            )
        else:
            budget_ok = True
        checks.append(
            _check(
                "agent_budget",
                budget_ok,
                {
                    "requested_notional": round(notional_requested, 2),
                    "budget": float(agent_payload["budget"]),
                },
            )
        )
        if not budget_ok:
            return _reject(
                requested=requested,
                actor=actor,
                tool=tool,
                agent=agent_payload,
                reason="AGENT_BUDGET_EXCEEDED",
                checks=checks,
            )

    state = ledger.portfolio_state()
    equity = ledger.estimated_equity()
    pos_now = ledger.position_quantity(sym)
    pos_after_requested = pos_now + qty if sd == OrderSide.BUY else pos_now - qty
    pr = ledger.policy_engine.check(
        symbol=sym,
        side=sd,
        quantity=qty,
        price=policy_price,
        state=state,
        position_after=pos_after_requested,
        daily_order_count=ledger._daily_order_count(),
        equity=equity,
    )
    checks.append(
        _check(
            "portfolio_policy",
            pr.allowed,
            {"reason": pr.reason.value if pr.reason else None},
        )
    )
    if not pr.allowed and pr.reason:
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason=pr.reason.value,
            checks=checks,
        )

    q_adj, gross_reason = clamp_quantity_for_gross_exposure(
        rules=ledger.policy_engine.rules,
        equity=equity,
        positions=state.positions,
        symbol=sym,
        side=sd,
        quantity=qty,
        price=policy_price,
    )
    checks.append(
        _check(
            "gross_exposure",
            gross_reason is None,
            {"adjusted_quantity": q_adj, "reason": gross_reason.value if gross_reason else None},
        )
    )
    if gross_reason is not None:
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason=gross_reason.value,
            checks=checks,
        )

    pos_after = pos_now + q_adj if sd == OrderSide.BUY else pos_now - q_adj
    rb = check_var_cvar_budget(
        ledger.conn,
        ledger.policy_engine.rules,
        state.positions,
        sym,
        sd,
        q_adj,
        policy_price,
    )
    checks.append(
        _check("var_cvar_budget", rb is None, {"reason": rb.value if rb else None})
    )
    if rb is not None:
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason=rb.value,
            checks=checks,
        )

    fill_price = ledger._apply_slippage(mark, sd, q_adj * mark)
    fill_notional = q_adj * fill_price
    fee = ledger._fee_amount(fill_notional)
    cash = ledger.get_cash()
    cash_ok = sd == OrderSide.SELL or cash + 1e-9 >= fill_notional + fee
    position_ok = sd == OrderSide.BUY or pos_now + 1e-9 >= q_adj
    checks.append(_check("cash", cash_ok, {"cash": round(cash, 2)}))
    checks.append(_check("position", position_ok, {"current_position": pos_now}))
    if not cash_ok:
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason="INSUFFICIENT_CASH",
            checks=checks,
        )
    if not position_ok:
        return _reject(
            requested=requested,
            actor=actor,
            tool=tool,
            agent=agent_payload,
            reason="INSUFFICIENT_POSITION",
            checks=checks,
        )

    gross_before = gross_notional(state.positions)
    gross_after = projected_gross_after_order(
        positions=state.positions,
        symbol=sym,
        side=sd,
        quantity=q_adj,
        price=policy_price,
    )
    gross_multiple_after = gross_after / equity if equity > 1e-9 else None
    concentration_after = (
        abs(pos_after * policy_price) / equity if equity > 1e-9 else None
    )
    would_resize = q_adj + 1e-9 < qty
    requires_approval = False
    approval_reasons: list[str] = []
    if agent_id is not None:
        if would_resize:
            requires_approval = True
            approval_reasons.append("SIZE_REDUCED_BY_RISK")
        cap = ledger.policy_engine.rules.max_gross_exposure_multiple
        if cap > 0 and gross_multiple_after is not None and gross_multiple_after >= cap * 0.8:
            requires_approval = True
            approval_reasons.append("NEAR_GROSS_EXPOSURE_LIMIT")
        max_agent_notional = float(agent_payload["max_order_notional"]) if agent_payload else 0.0
        if max_agent_notional > 0 and notional_requested >= (
            max_agent_notional * APPROVAL_NOTIONAL_FRACTION_OF_AGENT_LIMIT
        ):
            requires_approval = True
            approval_reasons.append("LARGE_AGENT_ORDER")

    decision = TradeDecision.ALLOW
    if would_resize:
        decision = TradeDecision.RESIZE
    if requires_approval:
        decision = TradeDecision.REQUIRE_APPROVAL

    return {
        "decision": decision.value,
        "allowed": decision in (TradeDecision.ALLOW, TradeDecision.RESIZE),
        "requires_approval": requires_approval,
        "reason": ",".join(approval_reasons) if approval_reasons else None,
        "actor": actor,
        "tool": tool,
        "agent": agent_payload,
        "requested_order": requested,
        "checks": checks,
        "symbol": sym,
        "side": sd.value,
        "order_kind": kind.value,
        "requested_quantity": qty,
        "adjusted_quantity": q_adj,
        "would_resize": would_resize,
        "estimated_mark_price": round(mark, 6),
        "estimated_fill_price": round(fill_price, 6),
        "projected_notional": round(q_adj * policy_price, 2),
        "estimated_fee": round(fee, 6),
        "current_position": pos_now,
        "projected_position": pos_after,
        "estimated_equity": round(equity, 2),
        "projected_gross_notional_before": round(gross_before, 2),
        "projected_gross_notional_after": round(gross_after, 2),
        "projected_gross_multiple_after": (
            round(gross_multiple_after, 4) if gross_multiple_after is not None else None
        ),
        "projected_concentration_after": (
            round(concentration_after, 4) if concentration_after is not None else None
        ),
        "risk_budget": build_risk_budget_section(
            ledger.conn, ledger.policy_engine.rules
        ),
    }


def record_agent_action(
    conn: sqlite3.Connection,
    *,
    actor: str,
    tool: str,
    action: str,
    decision: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> None:
    agent = decision.get("agent") or {}
    agent_id = agent.get("id")
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO agent_actions (
                ts, agent_id, actor, tool, action, decision, reason,
                payload_json, result_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now().isoformat(),
                int(agent_id) if agent_id is not None else None,
                actor,
                tool,
                action,
                str(decision.get("decision", "UNKNOWN")),
                decision.get("reason"),
                json.dumps(decision, sort_keys=True),
                json.dumps(result, sort_keys=True) if result is not None else None,
            ),
        )
        append_audit(
            conn,
            actor=actor,
            action=f"agent_{action}",
            payload={
                "tool": tool,
                "agent_id": agent_id,
                "decision": decision.get("decision"),
                "reason": decision.get("reason"),
            },
            result=result or {},
        )
        append_causal_event(
            conn,
            event_type=f"agent.{action}",
            actor=actor,
            agent_id=int(agent_id) if agent_id is not None else None,
            payload={
                "tool": tool,
                "action": action,
                "decision": decision,
                "result": result,
            },
            correlation_id=infer_correlation_id(
                decision, f"agent_action:{int(cur.lastrowid)}"
            ),
            source_table="agent_actions",
            source_id=int(cur.lastrowid),
        )


def list_recent_agent_actions(
    conn: sqlite3.Connection, limit: int = 50,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT aa.*, a.name AS agent_name
        FROM agent_actions aa
        LEFT JOIN agents a ON aa.agent_id = a.id
        ORDER BY aa.id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "ts": r["ts"],
                "agent_id": int(r["agent_id"]) if r["agent_id"] is not None else None,
                "agent_name": r["agent_name"],
                "actor": r["actor"],
                "tool": r["tool"],
                "action": r["action"],
                "decision": r["decision"],
                "reason": r["reason"],
                "payload": json.loads(r["payload_json"] or "{}"),
                "result": json.loads(r["result_json"] or "null"),
            }
        )
    return out
