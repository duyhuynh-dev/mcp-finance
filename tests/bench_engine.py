"""Performance benchmark suite for the trading engine.

Run:  python -m tests.bench_engine
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from finance_core.db import init_schema
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.risk import compute_risk_metrics
from finance_core.types import OrderSide


@contextmanager
def timer(label: str) -> Generator[dict[str, Any], None, None]:
    result: dict[str, Any] = {}
    start = time.perf_counter()
    yield result
    elapsed = time.perf_counter() - start
    result["elapsed_ms"] = round(elapsed * 1000, 2)
    result["label"] = label


def _ledger() -> Ledger:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    lg = Ledger(conn, quotes=MockQuoteProvider())
    lg.set_policy(PolicyEngine(PolicyRules.default()))
    return lg


def bench_order_throughput(n: int = 500) -> dict[str, Any]:
    lg = _ledger()
    lg.deposit(10_000_000)
    with timer(f"place {n} orders") as t:
        for i in range(n):
            lg.place_order(
                f"bench-{i}", "AAPL", OrderSide.BUY, 1,
            )
    t["orders"] = n
    t["orders_per_sec"] = round(n / (t["elapsed_ms"] / 1000), 1)
    return t


def bench_portfolio_state(n: int = 200) -> dict[str, Any]:
    lg = _ledger()
    lg.deposit(5_000_000)
    syms = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    for i, sym in enumerate(syms):
        lg.place_order(f"setup-{i}", sym, OrderSide.BUY, 50)

    with timer(f"portfolio_state x{n}") as t:
        for _ in range(n):
            lg.portfolio_state()
    t["iterations"] = n
    t["ops_per_sec"] = round(n / (t["elapsed_ms"] / 1000), 1)
    return t


def bench_risk_analytics() -> dict[str, Any]:
    lg = _ledger()
    lg.deposit(1_000_000)
    for i in range(100):
        side = OrderSide.BUY if i % 3 != 0 else OrderSide.SELL
        if side == OrderSide.SELL and lg.position_quantity("AAPL") < 1:
            side = OrderSide.BUY
        lg.place_order(f"risk-{i}", "AAPL", side, 5)

    with timer("compute_risk_metrics") as t:
        m = compute_risk_metrics(lg.conn)
    t["sharpe"] = round(m.sharpe_ratio, 4)
    return t


def bench_equity_series(n: int = 100) -> dict[str, Any]:
    lg = _ledger()
    lg.deposit(1_000_000)
    for i in range(50):
        lg.place_order(f"eq-{i}", "AAPL", OrderSide.BUY, 2)

    with timer(f"equity_series x{n}") as t:
        for _ in range(n):
            lg.equity_series(limit=500)
    t["iterations"] = n
    t["ops_per_sec"] = round(n / (t["elapsed_ms"] / 1000), 1)
    return t


def main() -> None:
    print("=" * 60)
    print("  Finance Stack - Performance Benchmarks")
    print("=" * 60)

    benchmarks = [
        bench_order_throughput,
        bench_portfolio_state,
        bench_risk_analytics,
        bench_equity_series,
    ]

    results = []
    for fn in benchmarks:
        r = fn()
        results.append(r)
        print(f"\n  {r['label']}")
        print(f"    Time: {r['elapsed_ms']}ms")
        for k, v in r.items():
            if k not in ("label", "elapsed_ms"):
                print(f"    {k}: {v}")

    print("\n" + "=" * 60)
    print("  Summary")
    print("-" * 60)
    for r in results:
        print(f"  {r['label']:.<40} {r['elapsed_ms']:>8.1f}ms")
    print("=" * 60)


if __name__ == "__main__":
    main()
