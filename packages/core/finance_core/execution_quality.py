"""Execution quality analytics from realized fills."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Any


def build_execution_quality(conn: sqlite3.Connection, limit_orders: int = 500) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT
            f.order_id, f.symbol, f.side, f.quantity, f.price, f.fee,
            o.created_at
        FROM fills f
        JOIN orders o ON o.id = f.order_id
        ORDER BY f.id DESC
        LIMIT ?
        """,
        (max(1, min(limit_orders * 5, 5000)),),
    ).fetchall()
    if not rows:
        return {
            "summary": {
                "orders_analyzed": 0,
                "fills_analyzed": 0,
                "notional": 0.0,
                "fees": 0.0,
                "fee_bps_realized": 0.0,
                "implementation_shortfall_bps": 0.0,
            },
            "by_symbol": [],
        }

    by_order: dict[int, list[sqlite3.Row]] = defaultdict(list)
    by_symbol: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "fills": 0.0,
            "notional": 0.0,
            "fees": 0.0,
            "buy_qty": 0.0,
            "sell_qty": 0.0,
            "buy_notional": 0.0,
            "sell_notional": 0.0,
        }
    )
    for r in rows:
        by_order[int(r["order_id"])].append(r)
        s = by_symbol[str(r["symbol"])]
        q = float(r["quantity"])
        p = float(r["price"])
        n = q * p
        s["fills"] += 1
        s["notional"] += n
        s["fees"] += float(r["fee"])
        if str(r["side"]) == "BUY":
            s["buy_qty"] += q
            s["buy_notional"] += n
        else:
            s["sell_qty"] += q
            s["sell_notional"] += n

    total_shortfall_nv = 0.0
    total_order_nv = 0.0
    order_ids = sorted(by_order.keys(), reverse=True)[:limit_orders]
    for oid in order_ids:
        fills = list(reversed(by_order[oid]))  # oldest -> newest
        if not fills:
            continue
        side = str(fills[0]["side"])
        bench = float(fills[0]["price"])
        nv = sum(float(f["quantity"]) * float(f["price"]) for f in fills)
        q = sum(float(f["quantity"]) for f in fills)
        if q <= 1e-12 or bench <= 1e-12:
            continue
        vwap = nv / q
        if side == "BUY":
            bps = (vwap - bench) / bench * 10_000.0
        else:
            bps = (bench - vwap) / bench * 10_000.0
        total_shortfall_nv += bps * nv
        total_order_nv += nv

    total_notional = sum(v["notional"] for v in by_symbol.values())
    total_fees = sum(v["fees"] for v in by_symbol.values())
    fee_bps = (total_fees / total_notional * 10_000.0) if total_notional > 1e-9 else 0.0
    is_bps = (total_shortfall_nv / total_order_nv) if total_order_nv > 1e-9 else 0.0

    syms: list[dict[str, Any]] = []
    for sym, v in sorted(by_symbol.items(), key=lambda x: x[1]["notional"], reverse=True):
        buy_avg = (v["buy_notional"] / v["buy_qty"]) if v["buy_qty"] > 1e-9 else None
        sell_avg = (v["sell_notional"] / v["sell_qty"]) if v["sell_qty"] > 1e-9 else None
        net_qty = v["buy_qty"] - v["sell_qty"]
        syms.append(
            {
                "symbol": sym,
                "fills": int(v["fills"]),
                "notional": round(v["notional"], 2),
                "fees": round(v["fees"], 6),
                "fee_bps_realized": round(
                    (v["fees"] / v["notional"] * 10_000.0) if v["notional"] > 1e-9 else 0.0,
                    4,
                ),
                "avg_buy_price": round(buy_avg, 4) if buy_avg is not None else None,
                "avg_sell_price": round(sell_avg, 4) if sell_avg is not None else None,
                "net_quantity": round(net_qty, 6),
            }
        )

    return {
        "summary": {
            "orders_analyzed": len(order_ids),
            "fills_analyzed": sum(int(v["fills"]) for v in by_symbol.values()),
            "notional": round(total_notional, 2),
            "fees": round(total_fees, 6),
            "fee_bps_realized": round(fee_bps, 4),
            "implementation_shortfall_bps": round(is_bps, 4),
        },
        "by_symbol": syms[:25],
    }
