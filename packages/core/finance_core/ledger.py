from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from finance_core.audit import append_audit
from finance_core.db import init_schema, transaction
from finance_core.market import MockQuoteProvider, QuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import (
    FillRecord,
    OrderKind,
    OrderRecord,
    OrderSide,
    OrderStatus,
    PlaceOrderResult,
    PortfolioState,
    Position,
    RejectionReason,
    utc_now,
)


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Ledger:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        quotes: QuoteProvider | None = None,
        policy: PolicyEngine | None = None,
    ) -> None:
        self._conn = conn
        self._quotes = quotes or MockQuoteProvider()
        self._policy = policy or PolicyEngine(PolicyRules.default())

    @classmethod
    def open(
        cls,
        db_path: str,
        *,
        quotes: QuoteProvider | None = None,
        policy: PolicyEngine | None = None,
    ) -> Ledger:
        from finance_core.db import connect

        conn = connect(db_path)
        init_schema(conn)
        return cls(conn, quotes=quotes, policy=policy)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy

    def set_policy(self, policy: PolicyEngine) -> None:
        self._policy = policy

    def _fee_amount(self, notional: float) -> float:
        bps = self._policy.rules.fee_bps
        return round(notional * bps / 10_000.0, 6)

    def deposit(self, amount: float, *, actor: str = "api") -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        with transaction(self._conn):
            row = self._conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
            assert row is not None
            new_cash = float(row["cash"]) + amount
            self._conn.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))
            append_audit(
                self._conn,
                actor=actor,
                action="deposit",
                payload={"amount": amount},
                result={"cash_after": new_cash},
            )
            self._maybe_snapshot_equity(new_cash)
        return new_cash

    def set_trading_enabled(self, enabled: bool, *, actor: str = "api") -> None:
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE account SET trading_enabled = ? WHERE id = 1",
                (1 if enabled else 0,),
            )
            append_audit(
                self._conn,
                actor=actor,
                action="set_trading_enabled",
                payload={"enabled": enabled},
                result={},
            )

    def get_trading_enabled(self) -> bool:
        row = self._conn.execute("SELECT trading_enabled FROM account WHERE id = 1").fetchone()
        assert row is not None
        return bool(row["trading_enabled"])

    def get_cash(self) -> float:
        row = self._conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        assert row is not None
        return float(row["cash"])

    def estimated_equity(self) -> float:
        """Mark-to-market equity using current quote provider prices."""
        cash = self.get_cash()
        equity = cash
        for sym, pos in self._positions_map().items():
            try:
                q = self._quotes.get_quote(sym)
                equity += pos.quantity * q.price
            except ValueError:
                pass
        return equity

    def _positions_map(self) -> dict[str, Position]:
        rows = self._conn.execute(
            """
            SELECT symbol,
                   SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS qty
            FROM fills
            GROUP BY symbol
            HAVING ABS(qty) > 1e-9
            """
        ).fetchall()
        out: dict[str, Position] = {}
        for r in rows:
            sym = r["symbol"]
            qty = float(r["qty"])
            if abs(qty) > 1e-9:
                out[sym] = Position(symbol=sym, quantity=qty)
        return out

    def position_quantity(self, symbol: str) -> float:
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END), 0) AS q
            FROM fills WHERE symbol = ?
            """,
            (symbol.upper(),),
        ).fetchone()
        assert row is not None
        return float(row["q"])

    def portfolio_state(self) -> PortfolioState:
        cash = self.get_cash()
        enabled = self.get_trading_enabled()
        positions = self._positions_map()
        return PortfolioState(
            cash=cash,
            trading_enabled=enabled,
            positions=positions,
            rules_version=self._policy.rules.version,
        )

    def _maybe_snapshot_equity(self, cash: float | None = None) -> None:
        if cash is None:
            cash = self.get_cash()
        positions = self._positions_map()
        m = self._quotes
        equity = cash
        for sym, pos in positions.items():
            try:
                q = m.get_quote(sym)
                equity += pos.quantity * q.price
            except ValueError:
                pass
        ts = utc_now().isoformat()
        self._conn.execute(
            "INSERT INTO equity_snapshots (ts, equity) VALUES (?, ?)",
            (ts, equity),
        )

    def place_order(
        self,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        *,
        order_kind: OrderKind = OrderKind.MARKET,
        limit_price: float | None = None,
        actor: str = "agent",
    ) -> PlaceOrderResult:
        sym = symbol.upper()
        existing = self._conn.execute(
            "SELECT * FROM orders WHERE client_order_id = ?",
            (client_order_id,),
        ).fetchone()
        if existing:
            return self._existing_result(existing)

        if quantity <= 0:
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.INVALID_QUANTITY,
                actor,
            )

        if order_kind == OrderKind.LIMIT and (
            limit_price is None or limit_price <= 0
        ):
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.INVALID_LIMIT_PRICE,
                actor,
            )

        if not self.get_trading_enabled():
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.TRADING_DISABLED,
                actor,
            )

        try:
            quote = self._quotes.get_quote(sym)
            price = quote.price
        except ValueError:
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.UNKNOWN_SYMBOL,
                actor,
            )

        policy_price = float(limit_price) if order_kind == OrderKind.LIMIT else price
        state = self.portfolio_state()
        pos_now = self.position_quantity(sym)
        if side == OrderSide.BUY:
            pos_after = pos_now + quantity
        else:
            pos_after = pos_now - quantity

        pr = self._policy.check(
            symbol=sym,
            side=side,
            quantity=quantity,
            price=policy_price,
            state=state,
            position_after=pos_after,
        )
        if not pr.allowed and pr.reason:
            return self._reject_new_order(
                client_order_id, sym, side, quantity, pr.reason, actor, price
            )

        if order_kind == OrderKind.LIMIT:
            return self._place_limit_order(
                client_order_id,
                sym,
                side,
                quantity,
                float(limit_price),
                price,
                actor,
            )

        notional = quantity * price
        fee = self._fee_amount(notional)
        cash = self.get_cash()
        if side == OrderSide.BUY and cash + 1e-9 < notional + fee:
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.INSUFFICIENT_CASH,
                actor,
                price,
            )
        if side == OrderSide.SELL and pos_now + 1e-9 < quantity:
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.INSUFFICIENT_POSITION,
                actor,
                price,
            )

        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO orders (
                    client_order_id, symbol, side, quantity,
                    status, rejection_reason, order_kind, limit_price, created_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, ?)
                """,
                (
                    client_order_id,
                    sym,
                    side.value,
                    quantity,
                    OrderStatus.FILLED.value,
                    OrderKind.MARKET.value,
                    utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            ts = utc_now().isoformat()
            self._conn.execute(
                """
                INSERT INTO fills (order_id, symbol, side, quantity, price, fee, filled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (oid, sym, side.value, quantity, price, fee, ts),
            )
            if side == OrderSide.BUY:
                new_cash = cash - notional - fee
            else:
                new_cash = cash + notional - fee
            self._conn.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))

            result = PlaceOrderResult(
                success=True,
                order_id=oid,
                status=OrderStatus.FILLED,
                fill_price=price,
                message="filled",
            )
            append_audit(
                self._conn,
                actor=actor,
                action="place_order",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "quantity": quantity,
                    "order_kind": OrderKind.MARKET.value,
                },
                result=result.to_audit_dict(),
            )
            self._maybe_snapshot_equity(new_cash)
        self._try_fill_pending_limit_orders()
        return result

    def _place_limit_order(
        self,
        client_order_id: str,
        sym: str,
        side: OrderSide,
        quantity: float,
        limit_px: float,
        last_px: float,
        actor: str,
    ) -> PlaceOrderResult:
        pos_now = self.position_quantity(sym)
        if side == OrderSide.SELL and pos_now + 1e-9 < quantity:
            return self._reject_new_order(
                client_order_id,
                sym,
                side,
                quantity,
                RejectionReason.INSUFFICIENT_POSITION,
                actor,
                last_px,
            )

        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO orders (
                    client_order_id, symbol, side, quantity,
                    status, rejection_reason, order_kind, limit_price, created_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    client_order_id,
                    sym,
                    side.value,
                    quantity,
                    OrderStatus.PENDING.value,
                    OrderKind.LIMIT.value,
                    limit_px,
                    utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            result = PlaceOrderResult(
                success=True,
                order_id=oid,
                status=OrderStatus.PENDING,
                fill_price=None,
                message="pending",
            )
            append_audit(
                self._conn,
                actor=actor,
                action="place_order",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "quantity": quantity,
                    "order_kind": OrderKind.LIMIT.value,
                    "limit_price": limit_px,
                },
                result=result.to_audit_dict(),
            )
        self._try_fill_pending_limit_orders()
        return result

    def _try_fill_pending_limit_orders(self) -> None:
        """Fill resting LIMIT orders when the last price crosses the limit."""
        pending = self._conn.execute(
            """
            SELECT * FROM orders
            WHERE status = ? AND order_kind = ?
            """,
            (OrderStatus.PENDING.value, OrderKind.LIMIT.value),
        ).fetchall()
        for row in pending:
            oid = int(row["id"])
            sym = row["symbol"]
            side = OrderSide(row["side"])
            qty = float(row["quantity"])
            lim = row["limit_price"]
            if lim is None:
                continue
            lim_f = float(lim)
            try:
                px = self._quotes.get_quote(sym).price
            except ValueError:
                continue
            fillable = (side == OrderSide.BUY and px <= lim_f) or (
                side == OrderSide.SELL and px >= lim_f
            )
            if not fillable:
                continue
            cash = self.get_cash()
            pos_now = self.position_quantity(sym)
            notional = qty * px
            fee = self._fee_amount(notional)
            if side == OrderSide.BUY and cash + 1e-9 < notional + fee:
                continue
            if side == OrderSide.SELL and pos_now + 1e-9 < qty:
                continue
            with transaction(self._conn):
                ts = utc_now().isoformat()
                self._conn.execute(
                    """
                    INSERT INTO fills (order_id, symbol, side, quantity, price, fee, filled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (oid, sym, side.value, qty, px, fee, ts),
                )
                if side == OrderSide.BUY:
                    new_cash = cash - notional - fee
                else:
                    new_cash = cash + notional - fee
                self._conn.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))
                self._conn.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (OrderStatus.FILLED.value, oid),
                )
                append_audit(
                    self._conn,
                    actor="ledger",
                    action="fill_limit_order",
                    payload={"order_id": oid, "price": px},
                    result={"fee": fee},
                )
                self._maybe_snapshot_equity(new_cash)

    def cancel_order(self, order_id: int, *, actor: str = "agent") -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT id, status FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if row is None:
            return {
                "ok": False,
                "reason": RejectionReason.ORDER_NOT_FOUND.value,
            }
        if OrderStatus(row["status"]) != OrderStatus.PENDING:
            return {
                "ok": False,
                "reason": RejectionReason.NOT_PENDING_CANCEL.value,
            }
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (OrderStatus.CANCELLED.value, order_id),
            )
            append_audit(
                self._conn,
                actor=actor,
                action="cancel_order",
                payload={"order_id": order_id},
                result={"ok": True},
            )
        return {"ok": True, "order_id": order_id}

    def _existing_result(self, row: sqlite3.Row) -> PlaceOrderResult:
        oid = int(row["id"])
        status = OrderStatus(row["status"])
        if status == OrderStatus.REJECTED:
            reason = RejectionReason(row["rejection_reason"]) if row["rejection_reason"] else None
            return PlaceOrderResult(
                success=False,
                order_id=oid,
                status=status,
                rejection_reason=reason,
                message="rejected (idempotent replay)",
            )
        if status == OrderStatus.PENDING:
            return PlaceOrderResult(
                success=True,
                order_id=oid,
                status=OrderStatus.PENDING,
                fill_price=None,
                message="pending (idempotent replay)",
            )
        fill = self._conn.execute(
            "SELECT price FROM fills WHERE order_id = ? LIMIT 1",
            (oid,),
        ).fetchone()
        price = float(fill["price"]) if fill else None
        return PlaceOrderResult(
            success=True,
            order_id=oid,
            status=OrderStatus.FILLED,
            fill_price=price,
            message="filled (idempotent replay)",
        )

    def _reject_new_order(
        self,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        reason: RejectionReason,
        actor: str,
        price: float | None = None,
    ) -> PlaceOrderResult:
        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO orders (
                    client_order_id, symbol, side, quantity,
                    status, rejection_reason, order_kind, limit_price, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    client_order_id,
                    symbol,
                    side.value,
                    quantity,
                    OrderStatus.REJECTED.value,
                    reason.value,
                    OrderKind.MARKET.value,
                    utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            result = PlaceOrderResult(
                success=False,
                order_id=oid,
                status=OrderStatus.REJECTED,
                rejection_reason=reason,
                fill_price=price,
                message=reason.value,
            )
            append_audit(
                self._conn,
                actor=actor,
                action="place_order",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                },
                result=result.to_audit_dict(),
            )
        return result

    def list_orders(self, limit: int = 50) -> list[OrderRecord]:
        rows = self._conn.execute(
            """
            SELECT id, client_order_id, symbol, side, quantity, status,
                   rejection_reason, order_kind, limit_price, created_at
            FROM orders ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_order(r) for r in rows]

    def list_fills(self, limit: int = 50) -> list[FillRecord]:
        rows = self._conn.execute(
            """
            SELECT id, order_id, symbol, side, quantity, price, fee, filled_at
            FROM fills ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[FillRecord] = []
        for r in rows:
            fee = float(r["fee"]) if "fee" in r.keys() and r["fee"] is not None else 0.0
            out.append(
                FillRecord(
                    id=int(r["id"]),
                    order_id=int(r["order_id"]),
                    symbol=r["symbol"],
                    side=OrderSide(r["side"]),
                    quantity=float(r["quantity"]),
                    price=float(r["price"]),
                    filled_at=_parse_dt(r["filled_at"]),
                    fee=fee,
                )
            )
        return out

    def equity_series(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT ts, equity FROM equity_snapshots ORDER BY id ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [{"ts": r["ts"], "equity": float(r["equity"])} for r in rows]


def _row_to_order(r: sqlite3.Row) -> OrderRecord:
    ok = r["order_kind"] if "order_kind" in r.keys() else None
    kind = OrderKind(ok) if ok else OrderKind.MARKET
    lp = r["limit_price"] if "limit_price" in r.keys() else None
    lim = float(lp) if lp is not None else None
    return OrderRecord(
        id=int(r["id"]),
        client_order_id=r["client_order_id"],
        symbol=r["symbol"],
        side=OrderSide(r["side"]),
        quantity=float(r["quantity"]),
        status=OrderStatus(r["status"]),
        rejection_reason=RejectionReason(r["rejection_reason"]) if r["rejection_reason"] else None,
        created_at=_parse_dt(r["created_at"]),
        order_kind=kind,
        limit_price=lim,
    )


def reset_demo_db(conn: sqlite3.Connection) -> None:
    """Clear trading data; used by API demo reset."""
    with transaction(conn):
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM fills")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM equity_snapshots")
        conn.execute("UPDATE account SET cash = 0, trading_enabled = 1 WHERE id = 1")
