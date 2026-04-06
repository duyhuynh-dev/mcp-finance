"""Statistical arbitrage — pairs trading via cointegration."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from finance_core.strategies.base import Signal, SignalDirection, Strategy


def _adf_test(series: np.ndarray) -> float:
    """Simplified Augmented Dickey-Fuller p-value for stationarity."""
    n = len(series)
    if n < 20:
        return 1.0
    diff = np.diff(series)
    lag = series[:-1]
    if np.std(lag) < 1e-10:
        return 1.0
    slope, _, _, p_value, _ = sp_stats.linregress(lag, diff)
    return p_value


def _half_life(spread: np.ndarray) -> float:
    """Mean-reversion half-life via OLS on lagged spread."""
    n = len(spread)
    if n < 10:
        return float("inf")
    lagged = spread[:-1]
    delta = np.diff(spread)
    if np.std(lagged) < 1e-10:
        return float("inf")
    slope, _, _, _, _ = sp_stats.linregress(lagged, delta)
    if slope >= 0:
        return float("inf")
    return -np.log(2) / slope


class PairsTradingStrategy(Strategy):
    def __init__(
        self,
        pairs: list[tuple[str, str]] | None = None,
        lookback: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        min_correlation: float = 0.7,
    ) -> None:
        self.pairs = pairs or [
            ("AAPL", "MSFT"),
            ("GOOGL", "META"),
            ("SPY", "QQQ"),
        ]
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.min_correlation = min_correlation

    @property
    def name(self) -> str:
        return "pairs_trading"

    @property
    def description(self) -> str:
        pair_str = ", ".join(f"{a}/{b}" for a, b in self.pairs)
        return f"Pairs trading ({pair_str}) with z-score entry at {self.entry_z}"

    @property
    def required_history(self) -> int:
        return self.lookback + 10

    @property
    def universe(self) -> list[str]:
        syms: set[str] = set()
        for a, b in self.pairs:
            syms.add(a)
            syms.add(b)
        return sorted(syms)

    def get_config(self) -> dict[str, Any]:
        return {
            "pairs": [list(p) for p in self.pairs],
            "lookback": self.lookback,
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
            "min_correlation": self.min_correlation,
        }

    def generate_signals(self, prices: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        for sym_a, sym_b in self.pairs:
            if sym_a not in prices.columns or sym_b not in prices.columns:
                continue

            a = prices[sym_a].dropna()
            b = prices[sym_b].dropna()
            min_len = min(len(a), len(b))
            if min_len < self.lookback:
                continue

            a = a.iloc[-self.lookback:]
            b = b.iloc[-self.lookback:]
            a_arr = a.values.astype(float)
            b_arr = b.values.astype(float)

            corr = np.corrcoef(a_arr, b_arr)[0, 1]
            if abs(corr) < self.min_correlation:
                continue

            slope, intercept, _, _, _ = sp_stats.linregress(b_arr, a_arr)
            spread = a_arr - (slope * b_arr + intercept)

            adf_p = _adf_test(spread)
            spread_mean = np.mean(spread)
            spread_std = np.std(spread)
            if spread_std < 1e-10:
                continue

            z = (spread[-1] - spread_mean) / spread_std
            hl = _half_life(spread)

            meta = {
                "pair": f"{sym_a}/{sym_b}",
                "correlation": round(corr, 4),
                "hedge_ratio": round(slope, 4),
                "spread_z": round(z, 4),
                "adf_pvalue": round(adf_p, 4),
                "half_life": round(hl, 2) if hl < 1000 else "inf",
                "cointegrated": adf_p < 0.05,
            }

            if z < -self.entry_z:
                strength = min(1.0, abs(z) / (self.entry_z * 2))
                signals.append(Signal(
                    symbol=sym_a,
                    direction=SignalDirection.LONG,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={**meta, "leg": "long_underperformer"},
                ))
                signals.append(Signal(
                    symbol=sym_b,
                    direction=SignalDirection.SHORT,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={**meta, "leg": "short_outperformer"},
                ))
            elif z > self.entry_z:
                strength = min(1.0, z / (self.entry_z * 2))
                signals.append(Signal(
                    symbol=sym_a,
                    direction=SignalDirection.SHORT,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={**meta, "leg": "short_overperformer"},
                ))
                signals.append(Signal(
                    symbol=sym_b,
                    direction=SignalDirection.LONG,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={**meta, "leg": "long_underperformer"},
                ))
            elif abs(z) < self.exit_z:
                signals.append(Signal(
                    symbol=sym_a,
                    direction=SignalDirection.FLAT,
                    strength=0.2,
                    strategy_name=self.name,
                    metadata={**meta, "leg": "close_spread"},
                ))

        return signals
