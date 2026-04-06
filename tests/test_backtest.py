"""Tests for the backtesting framework."""

from __future__ import annotations

from finance_core.backtest import BacktestConfig, generate_prices, run_backtest


def test_generate_prices():
    ticks = generate_prices(["AAPL"], steps=50, seed=1)
    assert len(ticks) == 50
    assert all(t.price > 0 for t in ticks)
    assert ticks[0].symbol == "AAPL"


def test_backtest_basic():
    config = BacktestConfig.from_dict({
        "name": "test_bt",
        "initial_cash": 100_000,
        "steps": 50,
        "seed": 42,
        "start_prices": {"AAPL": 180},
        "rules": [
            {"type": "buy_below", "symbol": "AAPL", "threshold": 175, "quantity": 10},
            {"type": "sell_above", "symbol": "AAPL", "threshold": 185, "quantity": 10},
        ],
    })
    result = run_backtest(config)
    assert result.steps == 50
    assert result.final_equity > 0
    assert len(result.equity_curve) > 0
    assert "AAPL" in result.price_history


def test_backtest_to_dict():
    config = BacktestConfig.from_dict({
        "name": "dict_test",
        "initial_cash": 50_000,
        "steps": 20,
        "seed": 7,
        "start_prices": {"ZZZ": 100},
        "rules": [
            {"type": "buy_below", "symbol": "ZZZ", "threshold": 95, "quantity": 5},
        ],
    })
    result = run_backtest(config)
    d = result.to_dict()
    assert "final_equity" in d
    assert "equity_curve" in d
    assert "sharpe_ratio" in d


def test_backtest_deterministic():
    cfg = {
        "name": "determ",
        "initial_cash": 100_000,
        "steps": 30,
        "seed": 42,
        "start_prices": {"AAPL": 180},
        "rules": [
            {"type": "buy_below", "symbol": "AAPL", "threshold": 175, "quantity": 5},
        ],
    }
    r1 = run_backtest(BacktestConfig.from_dict(cfg))
    r2 = run_backtest(BacktestConfig.from_dict(cfg))
    assert r1.final_equity == r2.final_equity
    assert r1.equity_curve == r2.equity_curve
