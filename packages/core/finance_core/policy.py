from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from finance_core.types import OrderSide, PortfolioState, RejectionReason


@dataclass(frozen=True)
class PolicyRules:
    """Versioned rules; load from dict/JSON for reproducibility."""

    version: str
    max_shares_per_symbol: float
    max_order_notional: float
    fee_bps: float = 0.0

    @staticmethod
    def default() -> PolicyRules:
        return PolicyRules(
            version="1",
            max_shares_per_symbol=1_000.0,
            max_order_notional=50_000.0,
            fee_bps=0.0,
        )


@dataclass
class PolicyResult:
    allowed: bool
    reason: RejectionReason | None = None


def load_rules_from_dict(data: dict[str, Any]) -> PolicyRules:
    return PolicyRules(
        version=str(data.get("version", "1")),
        max_shares_per_symbol=float(data["max_shares_per_symbol"]),
        max_order_notional=float(data["max_order_notional"]),
        fee_bps=float(data.get("fee_bps", 0.0)),
    )


class PolicyEngine:
    def __init__(self, rules: PolicyRules) -> None:
        self.rules = rules

    def check(
        self,
        *,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        state: PortfolioState,
        position_after: float,
    ) -> PolicyResult:
        if quantity <= 0:
            return PolicyResult(False, RejectionReason.INVALID_QUANTITY)

        notional = quantity * price
        if notional > self.rules.max_order_notional:
            return PolicyResult(False, RejectionReason.MAX_ORDER_NOTIONAL)

        if abs(position_after) > self.rules.max_shares_per_symbol:
            return PolicyResult(False, RejectionReason.MAX_SHARES_PER_SYMBOL)

        return PolicyResult(True, None)
