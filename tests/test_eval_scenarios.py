from __future__ import annotations

from pathlib import Path

from finance_core.eval_runner import discover_and_run, run_scenario_file

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios" / "eval"


def test_deposit_buy_scenario() -> None:
    r = run_scenario_file(SCENARIOS / "deposit_buy.json")
    assert r.passed, r.detail


def test_reject_over_limit() -> None:
    r = run_scenario_file(SCENARIOS / "reject_over_limit.json")
    assert r.passed, r.detail


def test_all_discovered_scenarios() -> None:
    results = discover_and_run(SCENARIOS)
    failed = [r for r in results if not r.passed]
    assert not failed, failed[0].detail if failed else ""

