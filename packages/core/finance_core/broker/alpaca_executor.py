"""Alpaca paper-trading order executor."""

from __future__ import annotations

import logging
import os
import time

from finance_core.broker.base import ExecutionMode, ExecutionResult, OrderExecutor

logger = logging.getLogger(__name__)


class AlpacaOrderExecutor(OrderExecutor):
    """Submits real orders to Alpaca's paper trading environment."""

    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from alpaca.trading.client import TradingClient

            key = os.environ.get("ALPACA_API_KEY", "")
            secret = os.environ.get("ALPACA_SECRET_KEY", "")
            paper = os.environ.get("ALPACA_PAPER", "true").lower() in (
                "1", "true", "yes",
            )
            if not key or not secret:
                raise ValueError(
                    "ALPACA_API_KEY and ALPACA_SECRET_KEY are required"
                )
            self._client = TradingClient(key, secret, paper=paper)
        return self._client

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.ALPACA_PAPER

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: float | None = None,
        time_in_force: str = "day",
    ) -> ExecutionResult:
        from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        client = self._ensure_client()
        sym = symbol.upper().strip()

        alpaca_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        tif = TimeInForce.DAY if time_in_force == "day" else TimeInForce.GTC

        if order_type.lower() == "limit" and limit_price is not None:
            request = LimitOrderRequest(
                symbol=sym,
                qty=quantity,
                side=alpaca_side,
                type=OrderType.LIMIT,
                time_in_force=tif,
                limit_price=limit_price,
            )
        else:
            request = MarketOrderRequest(
                symbol=sym,
                qty=quantity,
                side=alpaca_side,
                type=OrderType.MARKET,
                time_in_force=tif,
            )

        order = client.submit_order(request)
        broker_id = str(order.id)
        logger.info("Alpaca order submitted: %s %s %s qty=%s", sym, side, order_type, quantity)

        filled_qty = 0.0
        fill_price = 0.0
        if order.filled_qty:
            filled_qty = float(order.filled_qty)
        if order.filled_avg_price:
            fill_price = float(order.filled_avg_price)

        if order.status.value in ("filled", "partially_filled"):
            return ExecutionResult(
                filled=order.status.value == "filled",
                fill_price=fill_price,
                fill_quantity=filled_qty,
                remaining_quantity=max(0, quantity - filled_qty),
                broker_order_id=broker_id,
            )

        fill_price, filled_qty = self._poll_fill(broker_id, quantity)
        return ExecutionResult(
            filled=filled_qty >= quantity - 1e-9,
            fill_price=fill_price,
            fill_quantity=filled_qty,
            remaining_quantity=max(0, quantity - filled_qty),
            broker_order_id=broker_id,
        )

    def _poll_fill(
        self, broker_id: str, qty: float, max_wait: float = 10.0,
    ) -> tuple[float, float]:
        """Poll Alpaca for fill status with exponential backoff."""
        client = self._ensure_client()
        waited = 0.0
        interval = 0.5
        while waited < max_wait:
            time.sleep(interval)
            waited += interval
            order = client.get_order_by_id(broker_id)
            status = order.status.value
            if status == "filled":
                return (
                    float(order.filled_avg_price or 0),
                    float(order.filled_qty or qty),
                )
            if status in ("canceled", "expired", "rejected"):
                return (0.0, 0.0)
            interval = min(interval * 1.5, 2.0)
        filled = float(order.filled_qty or 0)
        price = float(order.filled_avg_price or 0)
        return (price, filled)

    def cancel_order(self, broker_order_id: str) -> bool:
        try:
            client = self._ensure_client()
            client.cancel_order_by_id(broker_order_id)
            return True
        except Exception as e:
            logger.warning("Alpaca cancel failed: %s", e)
            return False

    def get_account_info(self) -> dict:
        try:
            client = self._ensure_client()
            acct = client.get_account()
            return {
                "mode": self.mode.value,
                "connected": True,
                "equity": float(acct.equity),
                "buying_power": float(acct.buying_power),
                "cash": float(acct.cash),
                "day_trade_count": int(acct.daytrade_count),
                "pattern_day_trader": bool(acct.pattern_day_trader),
                "account_blocked": bool(acct.account_blocked),
                "trading_blocked": bool(acct.trading_blocked),
            }
        except Exception as e:
            return {
                "mode": self.mode.value,
                "connected": False,
                "error": str(e),
            }

    def list_open_stock_positions(self) -> list[dict]:
        """Open stock positions (qty, symbol) for reconciliation."""
        client = self._ensure_client()
        positions = client.get_all_positions()
        out: list[dict] = []
        for p in positions:
            out.append({
                "symbol": str(p.symbol),
                "qty": float(p.qty),
                "market_value": float(getattr(p, "market_value", 0) or 0),
            })
        return out
