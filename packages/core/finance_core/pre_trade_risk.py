"""Pre-trade gross exposure checks (optional reduce-to-fit vs hard reject)."""

from __future__ import annotations

from finance_core.policy import PolicyRules
from finance_core.types import OrderSide, Position, RejectionReason


def _gross_notional(positions: dict[str, Position]) -> float:
    return sum(abs(p.market_value) for p in positions.values())


def _gross_after_order(
    gross: float,
    symbol: str,
    side: OrderSide,
    quantity: float,
    price: float,
    positions: dict[str, Position],
) -> float:
    """Approximate post-trade gross notional (sum of abs position MV)."""
    trade_nv = quantity * price
    pos = positions.get(symbol)
    pos_mv = abs(pos.market_value) if pos else 0.0
    pos_qty = pos.quantity if pos else 0.0

    if side == OrderSide.BUY:
        return gross + trade_nv

    if pos_qty > 0:
        reduc = min(trade_nv, pos_mv)
        return max(0.0, gross - reduc)
    if pos_qty < 0:
        return gross + trade_nv
    return gross


def _within_gross_cap(gross_after: float, equity: float, max_multiple: float) -> bool:
    if max_multiple <= 0 or equity <= 1e-9:
        return True
    return (gross_after / equity) <= max_multiple + 1e-9


def clamp_quantity_for_gross_exposure(
    *,
    rules: PolicyRules,
    equity: float,
    positions: dict[str, Position],
    symbol: str,
    side: OrderSide,
    quantity: float,
    price: float,
) -> tuple[float, RejectionReason | None]:
    """
    If max_gross_exposure_multiple > 0, ensure gross_notional/equity <= cap.
    Reduces size iteratively; rejects if no positive size fits.
    """
    cap = rules.max_gross_exposure_multiple
    if cap <= 0 or quantity <= 0:
        return quantity, None

    gross = _gross_notional(positions)
    q = quantity
    for _ in range(40):
        g_after = _gross_after_order(gross, symbol, side, q, price, positions)
        if _within_gross_cap(g_after, equity, cap):
            return round(q, 8), None
        if q < 1e-8:
            return 0.0, RejectionReason.PRE_TRADE_GROSS_EXPOSURE
        q *= 0.5
    return 0.0, RejectionReason.PRE_TRADE_GROSS_EXPOSURE


def gross_notional(positions: dict[str, Position]) -> float:
    """Public helper for current gross notional."""
    return _gross_notional(positions)


def projected_gross_after_order(
    *,
    positions: dict[str, Position],
    symbol: str,
    side: OrderSide,
    quantity: float,
    price: float,
) -> float:
    """Public helper for post-trade gross notional approximation."""
    g = _gross_notional(positions)
    return _gross_after_order(g, symbol, side, quantity, price, positions)
