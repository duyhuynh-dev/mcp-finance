from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderKind(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class RejectionReason(StrEnum):
    DUPLICATE_CLIENT_ORDER_ID = "DUPLICATE_CLIENT_ORDER_ID"
    TRADING_DISABLED = "TRADING_DISABLED"
    UNKNOWN_SYMBOL = "UNKNOWN_SYMBOL"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    INSUFFICIENT_POSITION = "INSUFFICIENT_POSITION"
    MAX_SHARES_PER_SYMBOL = "MAX_SHARES_PER_SYMBOL"
    MAX_ORDER_NOTIONAL = "MAX_ORDER_NOTIONAL"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_LIMIT_PRICE = "INVALID_LIMIT_PRICE"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    NOT_PENDING_CANCEL = "NOT_PENDING_CANCEL"


@dataclass
class OrderRecord:
    id: int
    client_order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    status: OrderStatus
    rejection_reason: RejectionReason | None
    created_at: datetime
    order_kind: OrderKind = OrderKind.MARKET
    limit_price: float | None = None


@dataclass
class FillRecord:
    id: int
    order_id: int
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    filled_at: datetime
    fee: float = 0.0


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float | None = None


@dataclass
class PortfolioState:
    cash: float
    trading_enabled: bool
    positions: dict[str, Position] = field(default_factory=dict)
    rules_version: str = "1"


@dataclass
class PlaceOrderResult:
    success: bool
    order_id: int | None
    status: OrderStatus
    rejection_reason: RejectionReason | None = None
    fill_price: float | None = None
    message: str = ""

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "status": self.status.value,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "fill_price": self.fill_price,
            "message": self.message,
        }
