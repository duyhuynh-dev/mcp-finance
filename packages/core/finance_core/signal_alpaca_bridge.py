"""Optional forward of strategy signals to Alpaca paper (feature-flagged)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def forward_pending_strategy_signals(
    conn: sqlite3.Connection,
    executor: Any,
    *,
    max_rows: int = 25,
    max_qty: float = 5.0,
    strategies: set[str] | None = None,
) -> dict[str, Any]:
    """
    Submit LONG signals as small market BUYs; mark rows broker_forwarded.
    Requires AlpacaOrderExecutor and valid env keys.
    """
    rows = conn.execute(
        """
        SELECT * FROM strategy_signals
        WHERE broker_forwarded = 0
        ORDER BY id ASC
        LIMIT ?
        """,
        (max_rows,),
    ).fetchall()
    details: list[dict[str, Any]] = []
    for r in rows:
        strat = r["strategy_name"]
        if strategies is not None and strat not in strategies:
            continue
        sid = int(r["id"])
        if r["direction"] != "LONG":
            conn.execute(
                "UPDATE strategy_signals SET broker_forwarded = 1 WHERE id = ?",
                (sid,),
            )
            details.append({"signal_id": sid, "skipped": "not LONG"})
            continue
        sym = str(r["symbol"]).upper()
        qty = min(max_qty, max(1.0, round(float(r["strength"]) * 10.0, 2)))
        try:
            ex = executor.submit_order(sym, "BUY", qty, "market")
            details.append({
                "signal_id": sid,
                "symbol": sym,
                "qty": qty,
                "broker_order_id": getattr(ex, "broker_order_id", None),
            })
        except Exception as exc:
            logger.warning("Signal forward failed id=%s: %s", sid, exc)
            details.append({"signal_id": sid, "error": str(exc)})
            continue
        conn.execute(
            "UPDATE strategy_signals SET broker_forwarded = 1 WHERE id = ?",
            (sid,),
        )
    conn.commit()
    return {"count": len(details), "details": details}
