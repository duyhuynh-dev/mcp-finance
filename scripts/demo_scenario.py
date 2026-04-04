#!/usr/bin/env python3
"""Seed DB, deposit, place trades via core (no LLM). Run from repo root."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "packages", "core"))

from finance_core.ledger import Ledger, reset_demo_db
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.types import OrderSide


def main() -> None:
    db = os.environ.get("FINANCE_DB_PATH", os.path.join(ROOT, "data", "finance.db"))
    os.makedirs(os.path.dirname(db), exist_ok=True)
    lg = Ledger.open(db)
    lg.set_policy(PolicyEngine(PolicyRules.default()))
    reset_demo_db(lg.conn)
    lg.deposit(100_000.0, actor="demo_script")
    for cid, sym, side, qty in [
        ("demo-1", "AAPL", OrderSide.BUY, 10),
        ("demo-2", "MSFT", OrderSide.BUY, 5),
        ("demo-3", "AAPL", OrderSide.SELL, 2),
    ]:
        r = lg.place_order(cid, sym, side, qty, actor="demo_script")
        print(cid, r.to_audit_dict())
    s = lg.portfolio_state()
    print("cash", s.cash, "equity", lg.estimated_equity())


if __name__ == "__main__":
    main()
