"""Walk-forward research reports for built-in strategies."""

from __future__ import annotations

import json
import math
import random
import sqlite3
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from finance_core.causal import append_causal_event
from finance_core.db import transaction
from finance_core.strategies.base import SignalDirection, Strategy
from finance_core.strategies.mean_reversion import MeanReversionStrategy
from finance_core.strategies.ml_alpha import MLAlphaStrategy
from finance_core.strategies.momentum import MomentumStrategy
from finance_core.strategies.pairs import PairsTradingStrategy
from finance_core.strategies.portfolio_opt import OptMethod, PortfolioOptStrategy
from finance_core.types import utc_now

DEFAULT_UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "SPY", "QQQ"]


@dataclass
class WalkForwardConfig:
    strategy_name: str
    name: str = ""
    symbols: list[str] = field(default_factory=lambda: DEFAULT_UNIVERSE[:4])
    total_bars: int = 360
    train_bars: int = 120
    test_bars: int = 40
    step_bars: int = 40
    seed: int = 42
    drift: float = 0.00025
    volatility: float = 0.018
    correlation: float = 0.35
    start_prices: dict[str, float] = field(default_factory=dict)
    strategy_params: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> WalkForwardConfig:
        return WalkForwardConfig(
            strategy_name=str(d.get("strategy_name", "momentum")),
            name=str(d.get("name", "")),
            symbols=[str(s).upper() for s in d.get("symbols", DEFAULT_UNIVERSE[:4])],
            total_bars=int(d.get("total_bars", 360)),
            train_bars=int(d.get("train_bars", 120)),
            test_bars=int(d.get("test_bars", 40)),
            step_bars=int(d.get("step_bars", d.get("test_bars", 40))),
            seed=int(d.get("seed", 42)),
            drift=float(d.get("drift", 0.00025)),
            volatility=float(d.get("volatility", 0.018)),
            correlation=float(d.get("correlation", 0.35)),
            start_prices={
                str(k).upper(): float(v) for k, v in (d.get("start_prices") or {}).items()
            },
            strategy_params=dict(d.get("strategy_params") or {}),
        )

    def normalized(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "name": self.name,
            "symbols": self.symbols,
            "total_bars": self.total_bars,
            "train_bars": self.train_bars,
            "test_bars": self.test_bars,
            "step_bars": self.step_bars,
            "seed": self.seed,
            "drift": self.drift,
            "volatility": self.volatility,
            "correlation": self.correlation,
            "start_prices": self.start_prices,
            "strategy_params": self.strategy_params,
        }


def build_strategy(name: str, params: dict[str, Any] | None = None) -> Strategy:
    params = params or {}
    key = name.strip().lower()
    if key == "momentum":
        return MomentumStrategy(**params)
    if key == "mean_reversion":
        return MeanReversionStrategy(**params)
    if key == "pairs_trading":
        return PairsTradingStrategy(**params)
    if key == "ml_alpha":
        return MLAlphaStrategy(**params)
    if key == "portfolio_opt_max_sharpe":
        return PortfolioOptStrategy(method=OptMethod.MAX_SHARPE, **params)
    if key == "portfolio_opt_risk_parity":
        return PortfolioOptStrategy(method=OptMethod.RISK_PARITY, **params)
    if key == "portfolio_opt_min_variance":
        return PortfolioOptStrategy(method=OptMethod.MIN_VARIANCE, **params)
    raise ValueError(f"unknown strategy: {name}")


def available_research_strategies() -> list[dict[str, Any]]:
    out = []
    for name in [
        "momentum",
        "mean_reversion",
        "pairs_trading",
        "portfolio_opt_max_sharpe",
        "portfolio_opt_risk_parity",
        "portfolio_opt_min_variance",
        "ml_alpha",
    ]:
        s = build_strategy(name)
        out.append({
            "name": s.name,
            "description": s.description,
            "required_history": s.required_history,
            "config": s.get_config(),
        })
    return out


def generate_correlated_price_panel(cfg: WalkForwardConfig) -> pd.DataFrame:
    if len(cfg.symbols) < 1:
        raise ValueError("at least one symbol is required")
    if cfg.total_bars < cfg.train_bars + cfg.test_bars:
        raise ValueError("total_bars must cover at least one train/test window")
    rng = random.Random(cfg.seed)
    defaults = {
        "AAPL": 180.0,
        "MSFT": 380.0,
        "GOOGL": 140.0,
        "AMZN": 170.0,
        "NVDA": 900.0,
        "META": 480.0,
        "SPY": 500.0,
        "QQQ": 430.0,
    }
    prices = {
        s: float(cfg.start_prices.get(s, defaults.get(s, 100.0 + i * 20)))
        for i, s in enumerate(cfg.symbols)
    }
    corr = max(0.0, min(0.95, cfg.correlation))
    rows: list[dict[str, float]] = []
    for _ in range(cfg.total_bars):
        rows.append(dict(prices))
        market_shock = rng.gauss(0, 1)
        for i, sym in enumerate(cfg.symbols):
            idio = rng.gauss(0, 1)
            cyclical = math.sin(len(rows) / (18 + i * 4)) * cfg.volatility * 0.25
            shock = corr * market_shock + math.sqrt(1 - corr**2) * idio
            step = cfg.drift + cyclical - 0.5 * cfg.volatility**2 + cfg.volatility * shock
            prices[sym] = max(0.01, prices[sym] * math.exp(step))
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=cfg.total_bars, freq="D")
    return pd.DataFrame(rows, index=idx)


def _direction_exposure(direction: SignalDirection) -> float:
    if direction == SignalDirection.LONG:
        return 1.0
    if direction == SignalDirection.SHORT:
        return -1.0
    return 0.0


def _max_drawdown(curve: list[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    worst = 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst


def _metrics(returns: list[float]) -> dict[str, Any]:
    if not returns:
        return {
            "bars": 0,
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
        }
    arr = np.array(returns, dtype=float)
    curve = np.cumprod(1 + arr).tolist()
    total = float(curve[-1] - 1.0)
    mean = float(arr.mean())
    vol = float(arr.std())
    sharpe = (mean / vol) * math.sqrt(252) if vol > 1e-12 else 0.0
    hits = int((arr > 0).sum())
    return {
        "bars": len(returns),
        "total_return": round(total, 6),
        "annualized_return": round(((1 + total) ** (252 / len(returns))) - 1, 6),
        "annualized_volatility": round(vol * math.sqrt(252), 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(_max_drawdown(curve), 6),
        "hit_rate": round(hits / len(returns), 4),
    }


def run_walk_forward_report(cfg: WalkForwardConfig) -> dict[str, Any]:
    prices = generate_correlated_price_panel(cfg)
    strategy = build_strategy(cfg.strategy_name, cfg.strategy_params)
    if cfg.train_bars < strategy.required_history:
        raise ValueError(
            f"train_bars must be >= required_history ({strategy.required_history})"
        )

    all_returns: list[float] = []
    benchmark_returns: list[float] = []
    windows: list[dict[str, Any]] = []
    signal_counts: dict[str, int] = {}
    direction_counts = {"LONG": 0, "SHORT": 0, "FLAT": 0}
    exposure_sum = 0.0
    exposure_bars = 0
    turnover = 0.0
    prev_exposure: dict[str, float] = {s: 0.0 for s in cfg.symbols}
    latest_signals: list[dict[str, Any]] = []

    starts = range(
        cfg.train_bars,
        len(prices) - cfg.test_bars + 1,
        max(1, cfg.step_bars),
    )
    for window_idx, start in enumerate(starts, start=1):
        end = start + cfg.test_bars
        window_returns: list[float] = []
        window_signal_count = 0
        window_turnover = 0.0

        for i in range(start, end - 1):
            history = prices.iloc[: i + 1]
            signals = strategy.generate_signals(history)
            exposures = {s: 0.0 for s in cfg.symbols}
            for sig in signals:
                if sig.symbol not in exposures:
                    continue
                exp = _direction_exposure(sig.direction) * max(0.0, min(1.0, sig.strength))
                exposures[sig.symbol] = exp
                signal_counts[sig.symbol] = signal_counts.get(sig.symbol, 0) + 1
                direction_counts[sig.direction.value] += 1
                window_signal_count += 1
                latest_signals = [sig.to_dict(), *latest_signals][:10]

            ret_by_sym = (
                prices.iloc[i + 1][cfg.symbols] / prices.iloc[i][cfg.symbols] - 1.0
            )
            active = sum(1 for v in exposures.values() if abs(v) > 1e-12)
            bar_ret = 0.0
            if active:
                bar_ret = float(
                    sum(exposures[s] * float(ret_by_sym[s]) for s in cfg.symbols) / active
                )
            bench = float(ret_by_sym.mean())
            delta_turnover = sum(
                abs(exposures[s] - prev_exposure.get(s, 0.0)) for s in cfg.symbols
            )
            prev_exposure = exposures
            window_turnover += delta_turnover
            turnover += delta_turnover
            exposure_sum += sum(abs(v) for v in exposures.values()) / len(exposures)
            exposure_bars += 1
            all_returns.append(bar_ret)
            benchmark_returns.append(bench)
            window_returns.append(bar_ret)

        windows.append({
            "index": window_idx,
            "train_start": str(prices.index[start - cfg.train_bars].date()),
            "train_end": str(prices.index[start - 1].date()),
            "test_start": str(prices.index[start].date()),
            "test_end": str(prices.index[end - 1].date()),
            "signal_count": window_signal_count,
            "turnover": round(window_turnover, 4),
            "metrics": _metrics(window_returns),
        })

    report_metrics = _metrics(all_returns)
    benchmark_metrics = _metrics(benchmark_returns)
    excess = [a - b for a, b in zip(all_returns, benchmark_returns)]
    report = {
        "name": cfg.name or f"{strategy.name}_walk_forward",
        "strategy": {
            "name": strategy.name,
            "description": strategy.description,
            "required_history": strategy.required_history,
            "config": strategy.get_config(),
        },
        "methodology": {
            "type": "walk_forward",
            "train_bars": cfg.train_bars,
            "test_bars": cfg.test_bars,
            "step_bars": cfg.step_bars,
            "windows": len(windows),
            "data_source": "deterministic_correlated_synthetic_panel",
            "seed": cfg.seed,
            "note": "Signals are generated only from history available before each scored bar.",
        },
        "universe": cfg.symbols,
        "metrics": report_metrics,
        "benchmark": benchmark_metrics,
        "excess": _metrics(excess),
        "diagnostics": {
            "signal_counts_by_symbol": signal_counts,
            "direction_counts": direction_counts,
            "avg_abs_exposure": round(exposure_sum / exposure_bars, 6)
            if exposure_bars
            else 0.0,
            "turnover": round(turnover, 4),
            "latest_signals": latest_signals,
            "sample_size_warning": len(all_returns) < 100,
        },
        "windows": windows,
        "equity_curve": [round(v, 6) for v in np.cumprod(1 + np.array(all_returns)).tolist()],
        "benchmark_curve": [
            round(v, 6) for v in np.cumprod(1 + np.array(benchmark_returns)).tolist()
        ],
    }
    return report


def save_research_run(
    conn: sqlite3.Connection, cfg: WalkForwardConfig, report: dict[str, Any],
) -> dict[str, Any]:
    ts = utc_now().isoformat()
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO research_runs (
                name, strategy_name, config_json, report_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                report["name"],
                report["strategy"]["name"],
                json.dumps(cfg.normalized(), sort_keys=True),
                json.dumps(report, sort_keys=True),
                ts,
            ),
        )
        rid = int(cur.lastrowid)
        append_causal_event(
            conn,
            event_type="research.walk_forward_report_created",
            actor="research",
            payload={
                "research_run_id": rid,
                "name": report["name"],
                "strategy": report["strategy"]["name"],
                "metrics": report["metrics"],
                "methodology": report["methodology"],
            },
            correlation_id=f"research_run:{rid}",
            source_table="research_runs",
            source_id=rid,
        )
    return {"id": rid, "created_at": ts, **report}


def list_research_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, name, strategy_name, report_json, created_at
        FROM research_runs ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        report = json.loads(r["report_json"])
        out.append({
            "id": int(r["id"]),
            "name": r["name"],
            "strategy_name": r["strategy_name"],
            "created_at": r["created_at"],
            "metrics": report.get("metrics", {}),
            "benchmark": report.get("benchmark", {}),
            "diagnostics": report.get("diagnostics", {}),
            "methodology": report.get("methodology", {}),
        })
    return out


def get_research_run(conn: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM research_runs WHERE id = ?", (run_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "created_at": row["created_at"],
        "config": json.loads(row["config_json"]),
        **json.loads(row["report_json"]),
    }
