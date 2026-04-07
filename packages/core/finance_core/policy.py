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
    slippage_bps: float = 0.0
    slippage_impact_bps_per_million: float = 0.0
    max_daily_order_count: int = 0
    max_portfolio_concentration_pct: float = 0.0
    max_gross_exposure_multiple: float = 0.0
    # Historical equity-curve VaR(95)/CVaR(95) as fraction of equity; 0 = off.
    max_portfolio_var_95_pct_of_equity: float = 0.0
    max_portfolio_cvar_95_pct_of_equity: float = 0.0

    @staticmethod
    def default() -> PolicyRules:
        return PolicyRules(
            version="1",
            max_shares_per_symbol=1_000.0,
            max_order_notional=50_000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            slippage_impact_bps_per_million=0.0,
            max_daily_order_count=0,
            max_portfolio_concentration_pct=0.0,
            max_gross_exposure_multiple=0.0,
            max_portfolio_var_95_pct_of_equity=0.0,
            max_portfolio_cvar_95_pct_of_equity=0.0,
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
        slippage_bps=float(data.get("slippage_bps", 0.0)),
        slippage_impact_bps_per_million=float(
            data.get("slippage_impact_bps_per_million", 0.0)
        ),
        max_daily_order_count=int(data.get("max_daily_order_count", 0)),
        max_portfolio_concentration_pct=float(
            data.get("max_portfolio_concentration_pct", 0.0)
        ),
        max_gross_exposure_multiple=float(
            data.get("max_gross_exposure_multiple", 0.0)
        ),
        max_portfolio_var_95_pct_of_equity=float(
            data.get("max_portfolio_var_95_pct_of_equity", 0.0)
        ),
        max_portfolio_cvar_95_pct_of_equity=float(
            data.get("max_portfolio_cvar_95_pct_of_equity", 0.0)
        ),
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
        daily_order_count: int = 0,
        equity: float = 0.0,
    ) -> PolicyResult:
        if quantity <= 0:
            return PolicyResult(False, RejectionReason.INVALID_QUANTITY)

        notional = quantity * price
        if notional > self.rules.max_order_notional:
            return PolicyResult(False, RejectionReason.MAX_ORDER_NOTIONAL)

        if abs(position_after) > self.rules.max_shares_per_symbol:
            return PolicyResult(False, RejectionReason.MAX_SHARES_PER_SYMBOL)

        if (
            self.rules.max_daily_order_count > 0
            and daily_order_count >= self.rules.max_daily_order_count
        ):
            return PolicyResult(False, RejectionReason.MAX_DAILY_ORDERS)

        if (
            self.rules.max_portfolio_concentration_pct > 0
            and equity > 0
        ):
            post_notional = abs(position_after) * price
            concentration = (post_notional / equity) * 100.0
            if concentration > self.rules.max_portfolio_concentration_pct:
                return PolicyResult(False, RejectionReason.MAX_CONCENTRATION)

        return PolicyResult(True, None)
