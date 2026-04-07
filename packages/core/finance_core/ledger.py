from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from finance_core.audit import append_audit
from finance_core.broadcast import event_bus
from finance_core.db import init_schema, transaction
from finance_core.execution_events import append_execution_event
from finance_core.market import MockQuoteProvider, QuoteProvider
from finance_core.orderbook import LiquidityConfig, compute_fill_quantity
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.pre_trade_risk import clamp_quantity_for_gross_exposure
from finance_core.request_context import get_request_id
from finance_core.risk_budget import check_var_cvar_budget
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
    def quotes(self) -> QuoteProvider:
        return self._quotes

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy

    def set_policy(self, policy: PolicyEngine) -> None:
        self._policy = policy

    # ── helpers ───────────────────────────────────────────────

    def _fee_amount(self, notional: float) -> float:
        bps = self._policy.rules.fee_bps
        return round(notional * bps / 10_000.0, 6)

    def _apply_slippage(
        self, price: float, side: OrderSide, order_notional: float = 0.0,
    ) -> float:
        rules = self._policy.rules
        bps = float(rules.slippage_bps)
        if rules.slippage_impact_bps_per_million and order_notional > 0:
            bps += rules.slippage_impact_bps_per_million * (
                order_notional / 1_000_000.0
            )
        if bps == 0:
            return price
        factor = bps / 10_000.0
        if side == OrderSide.BUY:
            return round(price * (1.0 + factor), 6)
        return round(price * (1.0 - factor), 6)

    def _daily_order_count(self) -> int:
        """Count non-rejected orders placed today (UTC)."""
        today = utc_now().strftime("%Y-%m-%d")
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS c FROM orders
            WHERE created_at >= ? AND status != ?
            """,
            (today, OrderStatus.REJECTED.value),
        ).fetchone()
        return int(row["c"]) if row else 0

    # ── avg cost computation ─────────────────────────────────

    def _compute_avg_cost(self, symbol: str) -> float:
        """Walk fills in order to compute weighted-average cost basis."""
        rows = self._conn.execute(
            """
            SELECT side, quantity, price FROM fills
            WHERE symbol = ? ORDER BY id ASC
            """,
            (symbol,),
        ).fetchall()
        qty = 0.0
        cost_basis = 0.0
        for r in rows:
            s = r["side"]
            q = float(r["quantity"])
            p = float(r["price"])
            if s == OrderSide.BUY.value:
                cost_basis += q * p
                qty += q
            else:
                if qty > 1e-9:
                    avg = cost_basis / qty
                    cost_basis -= q * avg
                qty -= q
                if qty < 1e-9:
                    qty = 0.0
                    cost_basis = 0.0
        if qty > 1e-9:
            return round(cost_basis / qty, 6)
        return 0.0

    def _realized_pnl_for_sell(
        self, symbol: str, sell_price: float, sell_qty: float
    ) -> float:
        avg = self._compute_avg_cost(symbol)
        return round((sell_price - avg) * sell_qty, 6)

    def _total_realized_pnl(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(realized_pnl), 0) AS t FROM fills"
        ).fetchone()
        return float(row["t"]) if row else 0.0

    # ── account ───────────────────────────────────────────────

    def _emit(self, event_type: str, data: dict) -> None:
        evt: dict[str, Any] = {"type": event_type, **data}
        rid = get_request_id()
        if rid:
            evt["request_id"] = rid
        event_bus.publish(evt)

    def deposit(self, amount: float, *, actor: str = "api") -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        with transaction(self._conn):
            row = self._conn.execute(
                "SELECT cash FROM account WHERE id = 1"
            ).fetchone()
            assert row is not None
            new_cash = float(row["cash"]) + amount
            self._conn.execute(
                "UPDATE account SET cash = ? WHERE id = 1", (new_cash,)
            )
            append_audit(
                self._conn,
                actor=actor,
                action="deposit",
                payload={"amount": amount},
                result={"cash_after": new_cash},
            )
            self._maybe_snapshot_equity(new_cash)
        self._emit("deposit", {"amount": amount, "cash": new_cash, "actor": actor})
        return new_cash

    def set_trading_enabled(
        self, enabled: bool, *, actor: str = "api"
    ) -> None:
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
        row = self._conn.execute(
            "SELECT trading_enabled FROM account WHERE id = 1"
        ).fetchone()
        assert row is not None
        return bool(row["trading_enabled"])

    def get_cash(self) -> float:
        row = self._conn.execute(
            "SELECT cash FROM account WHERE id = 1"
        ).fetchone()
        assert row is not None
        return float(row["cash"])

    def estimated_equity(self) -> float:
        cash = self.get_cash()
        equity = cash
        for sym, pos in self._positions_map().items():
            try:
                q = self._quotes.get_quote(sym)
                equity += pos.quantity * q.price
            except ValueError:
                pass
        return equity

    # ── positions ─────────────────────────────────────────────

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
                avg = self._compute_avg_cost(sym)
                try:
                    q = self._quotes.get_quote(sym)
                    mark = q.price
                except ValueError:
                    mark = avg
                mv = qty * mark
                upnl = (mark - avg) * qty if avg > 0 else 0.0
                out[sym] = Position(
                    symbol=sym,
                    quantity=qty,
                    avg_cost=round(avg, 6),
                    mark_price=round(mark, 6),
                    market_value=round(mv, 2),
                    unrealized_pnl=round(upnl, 2),
                )
        return out

    def position_quantity(self, symbol: str) -> float:
        row = self._conn.execute(
            """
            SELECT COALESCE(
                SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END), 0
            ) AS q
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
        total_upnl = sum(p.unrealized_pnl for p in positions.values())
        return PortfolioState(
            cash=cash,
            trading_enabled=enabled,
            positions=positions,
            rules_version=self._policy.rules.version,
            total_realized_pnl=round(self._total_realized_pnl(), 2),
            total_unrealized_pnl=round(total_upnl, 2),
        )

    def _maybe_snapshot_equity(self, cash: float | None = None) -> None:
        if cash is None:
            cash = self.get_cash()
        positions = self._positions_map()
        equity = cash
        for pos in positions.values():
            equity += pos.market_value
        ts = utc_now().isoformat()
        self._conn.execute(
            "INSERT INTO equity_snapshots (ts, equity) VALUES (?, ?)",
            (ts, equity),
        )

    def snapshot_equity(self) -> None:
        """Record current equity into equity_snapshots."""
        with transaction(self._conn):
            self._maybe_snapshot_equity()

    # ── order placement ──────────────────────────────────────

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
        agent_id: int | None = None,
        liquidity: LiquidityConfig | None = None,
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
                client_order_id, sym, side, quantity,
                RejectionReason.INVALID_QUANTITY, actor,
            )

        if order_kind == OrderKind.LIMIT and (
            limit_price is None or limit_price <= 0
        ):
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.INVALID_LIMIT_PRICE, actor,
            )

        if not self.get_trading_enabled():
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.TRADING_DISABLED, actor,
            )

        try:
            quote = self._quotes.get_quote(sym)
            price = quote.price
        except ValueError:
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.UNKNOWN_SYMBOL, actor,
            )

        policy_price = (
            float(limit_price) if order_kind == OrderKind.LIMIT else price
        )
        state = self.portfolio_state()
        pos_now = self.position_quantity(sym)
        pos_after = (
            pos_now + quantity if side == OrderSide.BUY else pos_now - quantity
        )

        pr = self._policy.check(
            symbol=sym,
            side=side,
            quantity=quantity,
            price=policy_price,
            state=state,
            position_after=pos_after,
            daily_order_count=self._daily_order_count(),
            equity=self.estimated_equity(),
        )
        if not pr.allowed and pr.reason:
            return self._reject_new_order(
                client_order_id, sym, side, quantity, pr.reason, actor, price,
            )

        eq = self.estimated_equity()
        q_adj, rpre = clamp_quantity_for_gross_exposure(
            rules=self._policy.rules,
            equity=eq,
            positions=state.positions,
            symbol=sym,
            side=side,
            quantity=quantity,
            price=policy_price,
        )
        if rpre is not None:
            return self._reject_new_order(
                client_order_id, sym, side, quantity, rpre, actor, price,
            )
        if q_adj <= 0:
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.INVALID_QUANTITY, actor, price,
            )
        if q_adj + 1e-9 < quantity:
            quantity = q_adj
            pos_after = (
                pos_now + quantity if side == OrderSide.BUY else pos_now - quantity
            )
            pr2 = self._policy.check(
                symbol=sym,
                side=side,
                quantity=quantity,
                price=policy_price,
                state=state,
                position_after=pos_after,
                daily_order_count=self._daily_order_count(),
                equity=eq,
            )
            if not pr2.allowed and pr2.reason:
                return self._reject_new_order(
                    client_order_id, sym, side, quantity,
                    pr2.reason, actor, price,
                )

        rb = check_var_cvar_budget(
            self._conn,
            self._policy.rules,
            state.positions,
            sym,
            side,
            quantity,
            policy_price,
        )
        if rb is not None:
            return self._reject_new_order(
                client_order_id, sym, side, quantity, rb, actor, price,
            )

        if order_kind == OrderKind.LIMIT:
            return self._place_limit_order(
                client_order_id, sym, side, quantity,
                float(limit_price), price, actor, agent_id,
            )

        fill_price = self._apply_slippage(price, side, quantity * price)

        fill_qty = compute_fill_quantity(quantity, liquidity, sym)
        fill_qty = min(fill_qty, quantity)

        notional = fill_qty * fill_price
        fee = self._fee_amount(notional)
        cash = self.get_cash()

        if side == OrderSide.BUY and cash + 1e-9 < notional + fee:
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.INSUFFICIENT_CASH, actor, price,
            )
        if side == OrderSide.SELL and pos_now + 1e-9 < fill_qty:
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.INSUFFICIENT_POSITION, actor, price,
            )

        rpnl = 0.0
        if side == OrderSide.SELL:
            rpnl = self._realized_pnl_for_sell(sym, fill_price, fill_qty)

        remaining = round(quantity - fill_qty, 6)
        is_partial = remaining > 1e-9
        status = OrderStatus.PARTIAL if is_partial else OrderStatus.FILLED

        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO orders (
                    client_order_id, symbol, side, quantity,
                    status, rejection_reason, order_kind, limit_price,
                    agent_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?)
                """,
                (
                    client_order_id, sym, side.value, quantity,
                    status.value, OrderKind.MARKET.value,
                    agent_id, utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            ts = utc_now().isoformat()
            self._conn.execute(
                """
                INSERT INTO fills
                    (order_id, symbol, side, quantity, price, fee, realized_pnl, filled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (oid, sym, side.value, fill_qty, fill_price, fee, rpnl, ts),
            )
            if side == OrderSide.BUY:
                new_cash = cash - notional - fee
            else:
                new_cash = cash + notional - fee
            self._conn.execute(
                "UPDATE account SET cash = ? WHERE id = 1", (new_cash,)
            )

            msg = "partial_fill" if is_partial else "filled"
            result = PlaceOrderResult(
                success=True, order_id=oid, status=status,
                fill_price=fill_price,
                filled_quantity=fill_qty,
                remaining_quantity=remaining if is_partial else 0.0,
                message=msg,
            )
            append_audit(
                self._conn, actor=actor, action="place_order",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": sym, "side": side.value,
                    "quantity": quantity,
                    "order_kind": OrderKind.MARKET.value,
                },
                result=result.to_audit_dict(),
            )
            append_execution_event(
                self._conn,
                event_type="order_filled",
                payload={
                    "order_id": oid,
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "status": status.value,
                    "filled_quantity": fill_qty,
                    "remaining_quantity": remaining,
                    "fill_price": fill_price,
                },
            )
            self._maybe_snapshot_equity(new_cash)
        self._emit("fill", {
            "order_id": oid, "symbol": sym, "side": side.value,
            "quantity": fill_qty, "price": fill_price, "fee": fee,
            "remaining": remaining,
        })
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
        agent_id: int | None = None,
    ) -> PlaceOrderResult:
        pos_now = self.position_quantity(sym)
        if side == OrderSide.SELL and pos_now + 1e-9 < quantity:
            return self._reject_new_order(
                client_order_id, sym, side, quantity,
                RejectionReason.INSUFFICIENT_POSITION, actor, last_px,
            )

        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO orders (
                    client_order_id, symbol, side, quantity,
                    status, rejection_reason, order_kind, limit_price,
                    agent_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    client_order_id, sym, side.value, quantity,
                    OrderStatus.PENDING.value, OrderKind.LIMIT.value,
                    limit_px, agent_id, utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            result = PlaceOrderResult(
                success=True, order_id=oid, status=OrderStatus.PENDING,
                fill_price=None, message="pending",
            )
            append_audit(
                self._conn, actor=actor, action="place_order",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": sym, "side": side.value,
                    "quantity": quantity,
                    "order_kind": OrderKind.LIMIT.value,
                    "limit_price": limit_px,
                },
                result=result.to_audit_dict(),
            )
            append_execution_event(
                self._conn,
                event_type="order_opened",
                payload={
                    "order_id": oid,
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "status": OrderStatus.PENDING.value,
                    "quantity": quantity,
                    "order_kind": OrderKind.LIMIT.value,
                    "limit_price": limit_px,
                },
            )
        self._try_fill_pending_limit_orders()
        return result

    def _try_fill_pending_limit_orders(self) -> None:
        """Fill resting LIMIT orders when the last price crosses the limit."""
        pending = self._conn.execute(
            "SELECT * FROM orders WHERE status = ? AND order_kind = ?",
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
            fill_price = self._apply_slippage(px, side, qty * px)
            cash = self.get_cash()
            pos_now = self.position_quantity(sym)
            notional = qty * fill_price
            fee = self._fee_amount(notional)
            if side == OrderSide.BUY and cash + 1e-9 < notional + fee:
                continue
            if side == OrderSide.SELL and pos_now + 1e-9 < qty:
                continue
            rpnl = 0.0
            if side == OrderSide.SELL:
                rpnl = self._realized_pnl_for_sell(sym, fill_price, qty)
            with transaction(self._conn):
                ts = utc_now().isoformat()
                self._conn.execute(
                    """
                    INSERT INTO fills
                        (order_id, symbol, side, quantity, price, fee,
                         realized_pnl, filled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (oid, sym, side.value, qty, fill_price, fee, rpnl, ts),
                )
                if side == OrderSide.BUY:
                    new_cash = cash - notional - fee
                else:
                    new_cash = cash + notional - fee
                self._conn.execute(
                    "UPDATE account SET cash = ? WHERE id = 1", (new_cash,)
                )
                self._conn.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (OrderStatus.FILLED.value, oid),
                )
                append_audit(
                    self._conn, actor="ledger",
                    action="fill_limit_order",
                    payload={"order_id": oid, "price": fill_price},
                    result={"fee": fee, "realized_pnl": rpnl},
                )
                append_execution_event(
                    self._conn,
                    event_type="order_filled",
                    payload={
                        "order_id": oid,
                        "symbol": sym,
                        "side": side.value,
                        "status": OrderStatus.FILLED.value,
                        "filled_quantity": qty,
                        "remaining_quantity": 0.0,
                        "fill_price": fill_price,
                    },
                )
                self._maybe_snapshot_equity(new_cash)

    def sweep_partial_orders(
        self, liquidity: LiquidityConfig | None = None,
    ) -> list[dict[str, Any]]:
        """Try to fill remaining quantity on PARTIAL orders."""
        partials = self._conn.execute(
            "SELECT * FROM orders WHERE status = ?",
            (OrderStatus.PARTIAL.value,),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for row in partials:
            oid = int(row["id"])
            sym = row["symbol"]
            side = OrderSide(row["side"])
            total_qty = float(row["quantity"])

            filled_row = self._conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS fq FROM fills WHERE order_id = ?",
                (oid,),
            ).fetchone()
            already_filled = float(filled_row["fq"]) if filled_row else 0.0
            remaining = total_qty - already_filled
            if remaining < 1e-9:
                self._conn.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (OrderStatus.FILLED.value, oid),
                )
                continue

            try:
                px = self._quotes.get_quote(sym).price
            except ValueError:
                continue
            fill_price = self._apply_slippage(px, side, remaining * px)
            fill_qty = compute_fill_quantity(remaining, liquidity, sym)
            fill_qty = min(fill_qty, remaining)
            if fill_qty < 1e-9:
                continue

            notional = fill_qty * fill_price
            fee = self._fee_amount(notional)
            cash = self.get_cash()
            pos_now = self.position_quantity(sym)

            if side == OrderSide.BUY and cash + 1e-9 < notional + fee:
                continue
            if side == OrderSide.SELL and pos_now + 1e-9 < fill_qty:
                continue

            rpnl = 0.0
            if side == OrderSide.SELL:
                rpnl = self._realized_pnl_for_sell(sym, fill_price, fill_qty)

            new_remaining = round(remaining - fill_qty, 6)
            new_status = (
                OrderStatus.FILLED if new_remaining < 1e-9 else OrderStatus.PARTIAL
            )

            with transaction(self._conn):
                ts = utc_now().isoformat()
                self._conn.execute(
                    """INSERT INTO fills
                        (order_id, symbol, side, quantity, price, fee,
                         realized_pnl, filled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (oid, sym, side.value, fill_qty, fill_price, fee, rpnl, ts),
                )
                if side == OrderSide.BUY:
                    new_cash = cash - notional - fee
                else:
                    new_cash = cash + notional - fee
                self._conn.execute(
                    "UPDATE account SET cash = ? WHERE id = 1", (new_cash,)
                )
                self._conn.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (new_status.value, oid),
                )
                append_audit(
                    self._conn, actor="ledger", action="sweep_partial_fill",
                    payload={"order_id": oid, "fill_qty": fill_qty},
                    result={"fee": fee, "remaining": new_remaining},
                )
                append_execution_event(
                    self._conn,
                    event_type="order_filled",
                    payload={
                        "order_id": oid,
                        "symbol": sym,
                        "side": side.value,
                        "status": new_status.value,
                        "filled_quantity": fill_qty,
                        "remaining_quantity": new_remaining,
                        "fill_price": fill_price,
                    },
                )
                self._maybe_snapshot_equity(new_cash)
            self._emit("fill", {
                "order_id": oid, "symbol": sym, "side": side.value,
                "quantity": fill_qty, "price": fill_price,
                "remaining": new_remaining,
            })
            results.append({
                "order_id": oid, "filled": fill_qty,
                "remaining": new_remaining, "status": new_status.value,
            })
        return results

    def cancel_order(
        self, order_id: int, *, actor: str = "agent"
    ) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT id, status FROM orders WHERE id = ?", (order_id,),
        ).fetchone()
        if row is None:
            return {"ok": False, "reason": RejectionReason.ORDER_NOT_FOUND.value}
        status = OrderStatus(row["status"])
        if status not in (OrderStatus.PENDING, OrderStatus.PARTIAL):
            return {"ok": False, "reason": RejectionReason.NOT_PENDING_CANCEL.value}
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (OrderStatus.CANCELLED.value, order_id),
            )
            append_audit(
                self._conn, actor=actor, action="cancel_order",
                payload={"order_id": order_id}, result={"ok": True},
            )
            append_execution_event(
                self._conn,
                event_type="order_cancelled",
                payload={"order_id": order_id, "status": OrderStatus.CANCELLED.value},
            )
        self._emit("cancel", {"order_id": order_id})
        return {"ok": True, "order_id": order_id}

    def mirror_broker_execution(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        status: OrderStatus,
        fill_price: float | None = None,
        filled_quantity: float = 0.0,
        broker_order_id: str | None = None,
        actor: str = "broker_bridge",
        order_kind: OrderKind = OrderKind.MARKET,
        limit_price: float | None = None,
        agent_id: int | None = None,
        fees: float = 0.0,
    ) -> PlaceOrderResult:
        """Persist externally executed broker result into local ledger tables."""
        sym = symbol.upper()
        existing = self._conn.execute(
            "SELECT * FROM orders WHERE client_order_id = ?",
            (client_order_id,),
        ).fetchone()
        if existing:
            return self._existing_result(existing)

        q = float(quantity)
        fq = max(0.0, min(float(filled_quantity), q))
        rem = round(q - fq, 6)
        rpnl = 0.0
        if side == OrderSide.SELL and fq > 0 and fill_price is not None:
            rpnl = self._realized_pnl_for_sell(sym, float(fill_price), fq)

        with transaction(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO orders (
                    client_order_id, symbol, side, quantity,
                    status, rejection_reason, order_kind, limit_price,
                    agent_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    client_order_id,
                    sym,
                    side.value,
                    q,
                    status.value,
                    order_kind.value,
                    limit_price,
                    agent_id,
                    utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            new_cash = self.get_cash()
            if fq > 0 and fill_price is not None:
                notional = fq * float(fill_price)
                fee = float(fees) if fees > 0 else self._fee_amount(notional)
                self._conn.execute(
                    """
                    INSERT INTO fills
                        (order_id, symbol, side, quantity, price, fee, realized_pnl, filled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        oid,
                        sym,
                        side.value,
                        fq,
                        float(fill_price),
                        fee,
                        rpnl,
                        utc_now().isoformat(),
                    ),
                )
                if side == OrderSide.BUY:
                    new_cash = new_cash - notional - fee
                else:
                    new_cash = new_cash + notional - fee
                self._conn.execute(
                    "UPDATE account SET cash = ? WHERE id = 1",
                    (new_cash,),
                )
                self._maybe_snapshot_equity(new_cash)

            result = PlaceOrderResult(
                success=status != OrderStatus.REJECTED,
                order_id=oid,
                status=status,
                fill_price=float(fill_price) if fill_price is not None else None,
                filled_quantity=fq if fq > 0 else None,
                remaining_quantity=rem if rem > 0 else 0.0,
                message="broker_mirrored",
            )
            append_audit(
                self._conn,
                actor=actor,
                action="mirror_broker_execution",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "quantity": q,
                    "status": status.value,
                    "broker_order_id": broker_order_id,
                },
                result=result.to_audit_dict(),
            )
            append_execution_event(
                self._conn,
                event_type="order_filled" if fq > 0 else "order_opened",
                payload={
                    "order_id": oid,
                    "client_order_id": client_order_id,
                    "symbol": sym,
                    "side": side.value,
                    "status": status.value,
                    "filled_quantity": fq,
                    "remaining_quantity": rem,
                    "fill_price": float(fill_price) if fill_price is not None else None,
                    "broker_order_id": broker_order_id,
                },
            )

        if fq > 0 and fill_price is not None:
            self._emit(
                "fill",
                {
                    "order_id": oid,
                    "symbol": sym,
                    "side": side.value,
                    "quantity": fq,
                    "price": float(fill_price),
                    "remaining": rem,
                    "broker_order_id": broker_order_id,
                },
            )
        return result

    # ── idempotency helpers ──────────────────────────────────

    def _existing_result(self, row: sqlite3.Row) -> PlaceOrderResult:
        oid = int(row["id"])
        status = OrderStatus(row["status"])
        if status == OrderStatus.REJECTED:
            reason = (
                RejectionReason(row["rejection_reason"])
                if row["rejection_reason"]
                else None
            )
            return PlaceOrderResult(
                success=False, order_id=oid, status=status,
                rejection_reason=reason,
                message="rejected (idempotent replay)",
            )
        if status == OrderStatus.PENDING:
            return PlaceOrderResult(
                success=True, order_id=oid, status=OrderStatus.PENDING,
                fill_price=None, message="pending (idempotent replay)",
            )
        fill = self._conn.execute(
            "SELECT price, quantity FROM fills WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (oid,),
        ).fetchone()
        price = float(fill["price"]) if fill else None
        filled_row = self._conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS fq FROM fills WHERE order_id = ?",
            (oid,),
        ).fetchone()
        filled_qty = float(filled_row["fq"]) if filled_row else 0.0
        total_qty = float(row["quantity"])
        return PlaceOrderResult(
            success=True, order_id=oid, status=status,
            fill_price=price,
            filled_quantity=filled_qty,
            remaining_quantity=max(0.0, total_qty - filled_qty),
            message=f"{status.value.lower()} (idempotent replay)",
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
                    client_order_id, symbol, side.value, quantity,
                    OrderStatus.REJECTED.value, reason.value,
                    OrderKind.MARKET.value, utc_now().isoformat(),
                ),
            )
            oid = int(cur.lastrowid)
            result = PlaceOrderResult(
                success=False, order_id=oid, status=OrderStatus.REJECTED,
                rejection_reason=reason, fill_price=price,
                message=reason.value,
            )
            append_audit(
                self._conn, actor=actor, action="place_order",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": symbol, "side": side.value,
                    "quantity": quantity,
                },
                result=result.to_audit_dict(),
            )
            append_execution_event(
                self._conn,
                event_type="order_rejected",
                payload={
                    "order_id": oid,
                    "client_order_id": client_order_id,
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                    "rejection_reason": reason.value,
                },
            )
        return result

    # ── queries ───────────────────────────────────────────────

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
            SELECT id, order_id, symbol, side, quantity, price,
                   fee, realized_pnl, filled_at
            FROM fills ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[FillRecord] = []
        for r in rows:
            fee = _safe_float(r, "fee")
            rpnl = _safe_float(r, "realized_pnl")
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
                    realized_pnl=rpnl,
                )
            )
        return out

    def equity_series(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT ts, equity FROM (
                SELECT id, ts, equity FROM equity_snapshots
                ORDER BY id DESC LIMIT ?
            ) sub ORDER BY id ASC
            """,
            (limit,),
        ).fetchall()
        return [{"ts": r["ts"], "equity": float(r["equity"])} for r in rows]


def _safe_float(row: sqlite3.Row, col: str) -> float:
    try:
        v = row[col]
    except (IndexError, KeyError):
        return 0.0
    return float(v) if v is not None else 0.0


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
        rejection_reason=(
            RejectionReason(r["rejection_reason"])
            if r["rejection_reason"]
            else None
        ),
        created_at=_parse_dt(r["created_at"]),
        order_kind=kind,
        limit_price=lim,
    )


def reset_demo_db(conn: sqlite3.Connection) -> None:
    """Clear trading data; used by API demo reset."""
    with transaction(conn):
        conn.execute("DELETE FROM alert_notifications")
        conn.execute("DELETE FROM alert_rules")
        conn.execute("DELETE FROM backtest_runs")
        conn.execute("DELETE FROM strategy_signals")
        conn.execute("DELETE FROM strategy_configs")
        conn.execute("DELETE FROM price_history")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM fills")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM equity_snapshots")
        conn.execute("DELETE FROM agents")
        conn.execute("DELETE FROM api_keys")
        conn.execute(
            "UPDATE account SET cash = 0, trading_enabled = 1 WHERE id = 1"
        )
