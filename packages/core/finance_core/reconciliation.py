"""Compare internal ledger positions to Alpaca (when wired)."""

from __future__ import annotations

from typing import Any


def reconcile_ledger_vs_alpaca(ledger: Any) -> dict[str, Any]:
    from finance_core.broker.alpaca_executor import AlpacaOrderExecutor
    from finance_core.broker.alpaca_provider import AlpacaQuoteProvider
    from finance_core.market import CachedQuoteProvider

    internal: dict[str, float] = {}
    for sym, pos in ledger.portfolio_state().positions.items():
        internal[sym] = round(pos.quantity, 6)

    provider = ledger.quotes
    inner = provider._inner if isinstance(provider, CachedQuoteProvider) else provider
    if not isinstance(inner, AlpacaQuoteProvider):
        return {
            "enabled": False,
            "reason": "ledger quotes are not Alpaca-backed",
            "ledger_positions": internal,
        }

    try:
        exe = AlpacaOrderExecutor()
        broker = exe.list_open_stock_positions()
    except Exception as exc:
        return {
            "enabled": True,
            "error": str(exc),
            "ledger_positions": internal,
        }

    ext: dict[str, float] = {p["symbol"]: p["qty"] for p in broker}
    diffs: list[dict[str, Any]] = []
    all_syms = sorted(set(internal) | set(ext))
    for s in all_syms:
        li = internal.get(s, 0.0)
        bi = ext.get(s, 0.0)
        if abs(li - bi) > 1e-5:
            diffs.append({
                "symbol": s,
                "ledger_qty": li,
                "broker_qty": bi,
                "delta": round(li - bi, 6),
            })

    return {
        "enabled": True,
        "ledger_positions": internal,
        "broker_positions": ext,
        "mismatches": diffs,
        "in_sync": len(diffs) == 0,
    }
