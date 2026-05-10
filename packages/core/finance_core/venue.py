"""Execution venue simulation: lifecycle, spread, impact, latency, expiry."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from finance_core.causal import append_causal_event
from finance_core.db import transaction
from finance_core.ledger import Ledger
from finance_core.types import OrderKind, OrderSide, OrderStatus, utc_now


class VenueOrderStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


@dataclass
class VenueConfig:
    base_spread_bps: float = 8.0
    impact_bps_per_1000_shares: float = 2.5
    depth_per_tick: float = 40.0
    latency_ticks: int = 1
    default_tif_ticks: int = 5


def _emit(
    conn: sqlite3.Connection,
    event_type: str,
    payload: dict[str, Any],
    *,
    order_id: int | None = None,
) -> None:
    append_causal_event(
        conn,
        event_type=f"venue.{event_type}",
        actor="venue",
        payload=payload,
        correlation_id=f"client_order_id:{payload.get('client_order_id')}",
        source_table="venue_orders" if order_id else None,
        source_id=order_id,
    )


class SimulatedExecutionVenue:
    def __init__(self, ledger: Ledger, config: VenueConfig | None = None) -> None:
        self.ledger = ledger
        self.conn = ledger.conn
        self.config = config or VenueConfig()

    def submit_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderKind = OrderKind.MARKET,
        limit_price: float | None = None,
        time_in_force: str = "DAY",
    ) -> dict[str, Any]:
        sym = symbol.upper()
        now = utc_now().isoformat()
        expires = self.config.default_tif_ticks if time_in_force.upper() != "IOC" else 1
        latency = 0 if time_in_force.upper() == "IOC" else self.config.latency_ticks
        if quantity <= 0:
            status = VenueOrderStatus.REJECTED
        elif order_type == OrderKind.LIMIT and (limit_price is None or limit_price <= 0):
            status = VenueOrderStatus.REJECTED
        else:
            status = VenueOrderStatus.ACCEPTED
        with transaction(self.conn):
            cur = self.conn.execute(
                """
                INSERT INTO venue_orders (
                    client_order_id, symbol, side, quantity, order_type, limit_price,
                    time_in_force, status, filled_quantity, avg_fill_price,
                    expires_at_tick, current_tick, latency_ticks_remaining,
                    created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, 0, ?, ?, ?, ?)
                """,
                (
                    client_order_id,
                    sym,
                    side.value,
                    float(quantity),
                    order_type.value,
                    float(limit_price) if limit_price is not None else None,
                    time_in_force.upper(),
                    status.value,
                    expires,
                    latency,
                    now,
                    now,
                    json.dumps({"venue": "simulated"}),
                ),
            )
            oid = int(cur.lastrowid)
            _emit(
                self.conn,
                "order_accepted" if status != VenueOrderStatus.REJECTED else "order_rejected",
                {
                    "venue_order_id": oid,
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "quantity": quantity,
                    "order_type": order_type.value,
                    "limit_price": limit_price,
                    "status": status.value,
                },
                order_id=oid,
            )
        if status == VenueOrderStatus.ACCEPTED:
            return self.tick_order(oid)
        return self.get_order(oid) or {"error": "venue order not found"}

    def tick(self, max_orders: int = 100) -> dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT id FROM venue_orders
            WHERE status IN (?, ?, ?)
            ORDER BY id ASC LIMIT ?
            """,
            (
                VenueOrderStatus.ACCEPTED.value,
                VenueOrderStatus.OPEN.value,
                VenueOrderStatus.PARTIAL.value,
                max_orders,
            ),
        ).fetchall()
        results = [self.tick_order(int(r["id"])) for r in rows]
        return {"processed": len(results), "orders": results}

    def tick_order(self, order_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM venue_orders WHERE id = ?", (order_id,),
        ).fetchone()
        if row is None:
            return {"error": "venue order not found"}
        status = VenueOrderStatus(row["status"])
        if status in (
            VenueOrderStatus.FILLED,
            VenueOrderStatus.CANCELLED,
            VenueOrderStatus.EXPIRED,
            VenueOrderStatus.REJECTED,
        ):
            return self.get_order(order_id) or {}

        tick = int(row["current_tick"]) + 1
        latency = max(0, int(row["latency_ticks_remaining"]) - 1)
        if latency > 0:
            with transaction(self.conn):
                self.conn.execute(
                    """
                    UPDATE venue_orders
                    SET current_tick = ?, latency_ticks_remaining = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (tick, latency, VenueOrderStatus.OPEN.value, utc_now().isoformat(), order_id),
                )
                _emit(
                    self.conn,
                    "order_open",
                    {
                        "venue_order_id": order_id,
                        "client_order_id": row["client_order_id"],
                        "tick": tick,
                        "latency_ticks_remaining": latency,
                    },
                    order_id=order_id,
                )
            return self.get_order(order_id) or {}

        if row["expires_at_tick"] is not None and tick > int(row["expires_at_tick"]):
            with transaction(self.conn):
                self.conn.execute(
                    """
                    UPDATE venue_orders
                    SET status = ?, current_tick = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (VenueOrderStatus.EXPIRED.value, tick, utc_now().isoformat(), order_id),
                )
                _emit(
                    self.conn,
                    "order_expired",
                    {
                        "venue_order_id": order_id,
                        "client_order_id": row["client_order_id"],
                        "tick": tick,
                    },
                    order_id=order_id,
                )
            return self.get_order(order_id) or {}

        quote = self.ledger.quotes.get_quote(row["symbol"]).price
        side = OrderSide(row["side"])
        order_type = OrderKind(row["order_type"])
        limit_price = float(row["limit_price"]) if row["limit_price"] is not None else None
        bid = quote * (1 - self.config.base_spread_bps / 20_000)
        ask = quote * (1 + self.config.base_spread_bps / 20_000)
        executable = order_type == OrderKind.MARKET
        if order_type == OrderKind.LIMIT and limit_price is not None:
            executable = (side == OrderSide.BUY and ask <= limit_price) or (
                side == OrderSide.SELL and bid >= limit_price
            )
        if not executable:
            with transaction(self.conn):
                self.conn.execute(
                    """
                    UPDATE venue_orders
                    SET status = ?, current_tick = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (VenueOrderStatus.OPEN.value, tick, utc_now().isoformat(), order_id),
                )
            return self.get_order(order_id) or {}

        remaining = float(row["quantity"]) - float(row["filled_quantity"])
        fill_qty = min(remaining, self.config.depth_per_tick)
        impact_bps = self.config.impact_bps_per_1000_shares * (fill_qty / 1000)
        spread_px = ask if side == OrderSide.BUY else bid
        if side == OrderSide.BUY:
            fill_price = spread_px * (1 + impact_bps / 10_000)
        else:
            fill_price = spread_px * (1 - impact_bps / 10_000)
        fill_price = round(fill_price, 6)
        new_filled = float(row["filled_quantity"]) + fill_qty
        new_status = (
            VenueOrderStatus.FILLED
            if new_filled >= float(row["quantity"]) - 1e-9
            else VenueOrderStatus.PARTIAL
        )
        prior_avg = float(row["avg_fill_price"]) if row["avg_fill_price"] is not None else 0.0
        avg = (
            ((prior_avg * float(row["filled_quantity"])) + (fill_price * fill_qty))
            / new_filled
        )

        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO venue_fills (
                    venue_order_id, symbol, side, quantity, price,
                    spread_bps, impact_bps, tick, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    row["symbol"],
                    side.value,
                    fill_qty,
                    fill_price,
                    self.config.base_spread_bps,
                    impact_bps,
                    tick,
                    utc_now().isoformat(),
                ),
            )
            self.conn.execute(
                """
                UPDATE venue_orders
                SET status = ?, filled_quantity = ?, avg_fill_price = ?,
                    current_tick = ?, latency_ticks_remaining = 0, updated_at = ?
                WHERE id = ?
                """,
                (new_status.value, new_filled, avg, tick, utc_now().isoformat(), order_id),
            )
            _emit(
                self.conn,
                "fill",
                {
                    "venue_order_id": order_id,
                    "client_order_id": row["client_order_id"],
                    "symbol": row["symbol"],
                    "side": side.value,
                    "quantity": fill_qty,
                    "price": fill_price,
                    "spread_bps": self.config.base_spread_bps,
                    "impact_bps": impact_bps,
                    "status": new_status.value,
                    "tick": tick,
                },
                order_id=order_id,
            )

        mirror = self.ledger.mirror_broker_execution(
            client_order_id=f"venue-{row['client_order_id']}-{tick}",
            symbol=row["symbol"],
            side=side,
            quantity=fill_qty,
            status=OrderStatus.FILLED,
            fill_price=fill_price,
            filled_quantity=fill_qty,
            broker_order_id=f"SIM-{order_id}-{tick}",
            actor="venue",
            order_kind=order_type,
            limit_price=limit_price,
        )
        out = self.get_order(order_id) or {}
        out["ledger_mirror"] = mirror.to_audit_dict()
        return out

    def cancel_order(self, order_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM venue_orders WHERE id = ?", (order_id,),
        ).fetchone()
        if row is None:
            return {"ok": False, "error": "venue order not found"}
        if row["status"] not in (
            VenueOrderStatus.ACCEPTED.value,
            VenueOrderStatus.OPEN.value,
            VenueOrderStatus.PARTIAL.value,
        ):
            return {"ok": False, "error": "order is terminal", "status": row["status"]}
        with transaction(self.conn):
            self.conn.execute(
                "UPDATE venue_orders SET status = ?, updated_at = ? WHERE id = ?",
                (VenueOrderStatus.CANCELLED.value, utc_now().isoformat(), order_id),
            )
            _emit(
                self.conn,
                "order_cancelled",
                {
                    "venue_order_id": order_id,
                    "client_order_id": row["client_order_id"],
                    "status": VenueOrderStatus.CANCELLED.value,
                },
                order_id=order_id,
            )
        return {"ok": True, "order": self.get_order(order_id)}

    def get_order(self, order_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM venue_orders WHERE id = ?", (order_id,),
        ).fetchone()
        if row is None:
            return None
        fills = self.conn.execute(
            "SELECT * FROM venue_fills WHERE venue_order_id = ? ORDER BY id ASC",
            (order_id,),
        ).fetchall()
        return {
            "id": int(row["id"]),
            "client_order_id": row["client_order_id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "quantity": float(row["quantity"]),
            "order_type": row["order_type"],
            "limit_price": float(row["limit_price"]) if row["limit_price"] is not None else None,
            "time_in_force": row["time_in_force"],
            "status": row["status"],
            "filled_quantity": float(row["filled_quantity"]),
            "remaining_quantity": round(float(row["quantity"]) - float(row["filled_quantity"]), 6),
            "avg_fill_price": (
                float(row["avg_fill_price"])
                if row["avg_fill_price"] is not None
                else None
            ),
            "expires_at_tick": row["expires_at_tick"],
            "current_tick": int(row["current_tick"]),
            "latency_ticks_remaining": int(row["latency_ticks_remaining"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "fills": [
                {
                    "id": int(f["id"]),
                    "quantity": float(f["quantity"]),
                    "price": float(f["price"]),
                    "spread_bps": float(f["spread_bps"]),
                    "impact_bps": float(f["impact_bps"]),
                    "tick": int(f["tick"]),
                    "created_at": f["created_at"],
                }
                for f in fills
            ],
        }

    def list_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id FROM venue_orders ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self.get_order(int(r["id"])) for r in rows if self.get_order(int(r["id"]))]

    def status(self) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS c FROM venue_orders GROUP BY status"
        ).fetchall()
        fills = self.conn.execute(
            """
            SELECT COUNT(*) AS fills,
                   COALESCE(SUM(quantity), 0) AS qty,
                   COALESCE(AVG(spread_bps), 0) AS spread,
                   COALESCE(AVG(impact_bps), 0) AS impact
            FROM venue_fills
            """
        ).fetchone()
        return {
            "mode": "simulated",
            "config": self.config.__dict__,
            "orders_by_status": {r["status"]: int(r["c"]) for r in rows},
            "fills": {
                "count": int(fills["fills"]) if fills else 0,
                "quantity": float(fills["qty"]) if fills else 0.0,
                "avg_spread_bps": round(float(fills["spread"]), 4) if fills else 0.0,
                "avg_impact_bps": round(float(fills["impact"]), 4) if fills else 0.0,
            },
        }
