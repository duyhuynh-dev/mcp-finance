"""Smoke: MCP server modules import and stack health runs."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_portfolio_mcp_importable() -> None:
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    mod = importlib.import_module("servers.portfolio_mcp")
    assert mod.mcp is not None


def test_market_mcp_importable() -> None:
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    mod = importlib.import_module("servers.market_mcp")
    assert mod.mcp is not None


def test_finance_stack_health_uses_db(tmp_path) -> None:
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    name = "servers.portfolio_mcp"
    if name in sys.modules:
        del sys.modules[name]
    db = tmp_path / "smoke.db"
    quotes = MockQuoteProvider({"AAPL": 180.0})
    policy = PolicyEngine(
        PolicyRules(
            version="t",
            max_shares_per_symbol=1000.0,
            max_order_notional=50_000.0,
            fee_bps=10.0,
            slippage_bps=5.0,
        )
    )
    Ledger.open(str(db), quotes=quotes, policy=policy)

    import os

    os.environ["FINANCE_DB_PATH"] = str(db)
    mod = importlib.import_module(name)
    mod._ledger = None
    mod._strategy_engine = None
    h = mod.finance_stack_health()
    assert h["database"] == "ok"
    assert h["status"] == "ok"
    assert h["strategy_engine"]["initialized"] is True
