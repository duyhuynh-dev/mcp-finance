from __future__ import annotations

import sqlite3

from finance_core.db import init_schema
from finance_core.research import (
    WalkForwardConfig,
    get_research_run,
    list_research_runs,
    run_walk_forward_report,
    save_research_run,
)


def test_walk_forward_report_has_out_of_sample_windows():
    cfg = WalkForwardConfig(
        strategy_name="mean_reversion",
        symbols=["AAPL", "MSFT", "SPY"],
        total_bars=180,
        train_bars=80,
        test_bars=25,
        step_bars=25,
        seed=11,
    )
    report = run_walk_forward_report(cfg)
    assert report["methodology"]["type"] == "walk_forward"
    assert report["methodology"]["windows"] >= 3
    assert report["metrics"]["bars"] > 0
    assert "benchmark" in report
    assert "excess" in report
    assert "signal_counts_by_symbol" in report["diagnostics"]
    first = report["windows"][0]
    assert first["train_end"] < first["test_start"]


def test_research_run_persistence_round_trip():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    cfg = WalkForwardConfig(
        strategy_name="momentum",
        symbols=["AAPL", "MSFT"],
        total_bars=160,
        train_bars=70,
        test_bars=20,
        step_bars=20,
    )
    report = run_walk_forward_report(cfg)
    saved = save_research_run(conn, cfg, report)
    listed = list_research_runs(conn)
    detail = get_research_run(conn, saved["id"])
    assert listed[0]["id"] == saved["id"]
    assert detail is not None
    assert detail["strategy"]["name"] == "momentum"
    assert detail["metrics"]["bars"] == saved["metrics"]["bars"]
