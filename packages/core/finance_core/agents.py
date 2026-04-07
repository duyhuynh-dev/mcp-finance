"""Multi-agent orchestration: named agents with budgets, symbol restrictions, and scoped queries."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from finance_core.db import transaction
from finance_core.types import utc_now


@dataclass
class Agent:
    id: int
    name: str
    budget: float
    max_order_notional: float
    allowed_symbols: list[str]
    is_active: bool
    created_at: str
    allowed_mcp_tools: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "budget": self.budget,
            "max_order_notional": self.max_order_notional,
            "allowed_symbols": self.allowed_symbols,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "allowed_mcp_tools": self.allowed_mcp_tools,
        }


@dataclass
class AgentStats:
    agent_id: int
    agent_name: str
    total_orders: int = 0
    filled_orders: int = 0
    rejected_orders: int = 0
    total_notional: float = 0.0
    total_fees: float = 0.0
    realized_pnl: float = 0.0
    budget_used: float = 0.0
    budget_remaining: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "total_orders": self.total_orders,
            "filled_orders": self.filled_orders,
            "rejected_orders": self.rejected_orders,
            "total_notional": round(self.total_notional, 2),
            "total_fees": round(self.total_fees, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "budget_used": round(self.budget_used, 2),
            "budget_remaining": round(self.budget_remaining, 2),
            "positions": {k: round(v, 6) for k, v in self.positions.items()},
        }


class AgentManager:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def register(
        self,
        name: str,
        budget: float,
        max_order_notional: float = 50_000.0,
        allowed_symbols: list[str] | None = None,
        allowed_mcp_tools: list[str] | None = None,
    ) -> Agent:
        ts = utc_now().isoformat()
        syms_json = json.dumps(allowed_symbols or [])
        tools_json = (
            json.dumps(allowed_mcp_tools) if allowed_mcp_tools is not None else None
        )
        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO agents (name, budget, max_order_notional,
                                    allowed_symbols_json, allowed_mcp_tools_json,
                                    is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (name, budget, max_order_notional, syms_json, tools_json, ts),
            )
            return Agent(
                id=int(cur.lastrowid),
                name=name,
                budget=budget,
                max_order_notional=max_order_notional,
                allowed_symbols=allowed_symbols or [],
                is_active=True,
                created_at=ts,
                allowed_mcp_tools=allowed_mcp_tools,
            )

    def get(self, agent_id: int) -> Agent | None:
        row = self._conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        return _row_to_agent(row) if row else None

    def get_by_name(self, name: str) -> Agent | None:
        row = self._conn.execute(
            "SELECT * FROM agents WHERE name = ?", (name,)
        ).fetchone()
        return _row_to_agent(row) if row else None

    def list_all(self) -> list[Agent]:
        rows = self._conn.execute(
            "SELECT * FROM agents ORDER BY id ASC"
        ).fetchall()
        return [_row_to_agent(r) for r in rows]

    def set_active(self, agent_id: int, active: bool) -> None:
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE agents SET is_active = ? WHERE id = ?",
                (1 if active else 0, agent_id),
            )

    def check_budget(self, agent_id: int, notional: float) -> bool:
        """Check if agent has enough budget remaining for this trade."""
        agent = self.get(agent_id)
        if agent is None or not agent.is_active:
            return False
        used = self._budget_used(agent_id)
        return used + notional <= agent.budget

    def check_symbol_allowed(self, agent_id: int, symbol: str) -> bool:
        agent = self.get(agent_id)
        if agent is None:
            return False
        if not agent.allowed_symbols:
            return True
        return symbol.upper() in [s.upper() for s in agent.allowed_symbols]

    def _budget_used(self, agent_id: int) -> float:
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(f.quantity * f.price), 0) AS used
            FROM fills f
            JOIN orders o ON f.order_id = o.id
            WHERE o.agent_id = ? AND f.side = 'BUY'
            """,
            (agent_id,),
        ).fetchone()
        return float(row["used"]) if row else 0.0

    def stats(self, agent_id: int) -> AgentStats | None:
        agent = self.get(agent_id)
        if agent is None:
            return None
        s = AgentStats(agent_id=agent.id, agent_name=agent.name)

        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        s.total_orders = int(row["c"]) if row else 0

        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE agent_id = ? AND status = 'FILLED'",
            (agent_id,),
        ).fetchone()
        s.filled_orders = int(row["c"]) if row else 0

        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE agent_id = ? AND status = 'REJECTED'",
            (agent_id,),
        ).fetchone()
        s.rejected_orders = int(row["c"]) if row else 0

        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(f.quantity * f.price), 0) AS notional,
                   COALESCE(SUM(f.fee), 0) AS fees,
                   COALESCE(SUM(f.realized_pnl), 0) AS rpnl
            FROM fills f
            JOIN orders o ON f.order_id = o.id
            WHERE o.agent_id = ?
            """,
            (agent_id,),
        ).fetchone()
        if row:
            s.total_notional = float(row["notional"])
            s.total_fees = float(row["fees"])
            s.realized_pnl = float(row["rpnl"])

        s.budget_used = self._budget_used(agent_id)
        s.budget_remaining = agent.budget - s.budget_used

        pos_rows = self._conn.execute(
            """
            SELECT f.symbol,
                   SUM(CASE WHEN f.side='BUY' THEN f.quantity ELSE -f.quantity END) AS qty
            FROM fills f
            JOIN orders o ON f.order_id = o.id
            WHERE o.agent_id = ?
            GROUP BY f.symbol
            HAVING ABS(qty) > 1e-9
            """,
            (agent_id,),
        ).fetchall()
        for pr in pos_rows:
            s.positions[pr["symbol"]] = float(pr["qty"])

        return s


def _row_to_agent(row: sqlite3.Row) -> Agent:
    syms_raw = row["allowed_symbols_json"]
    syms = json.loads(syms_raw) if syms_raw else []
    tools: list[str] | None = None
    keys = row.keys()
    if "allowed_mcp_tools_json" in keys and row["allowed_mcp_tools_json"]:
        raw = json.loads(row["allowed_mcp_tools_json"])
        tools = [str(x) for x in raw] if isinstance(raw, list) else None
    return Agent(
        id=int(row["id"]),
        name=row["name"],
        budget=float(row["budget"]),
        max_order_notional=float(row["max_order_notional"]),
        allowed_symbols=syms,
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        allowed_mcp_tools=tools,
    )
