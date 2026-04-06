"""Momentum / trend-following strategy — dual EMA crossover + RSI + MACD."""

from __future__ import annotations

from typing import Any

import pandas as pd

from finance_core.strategies.base import (
    Signal,
    SignalDirection,
    Strategy,
    ema,
    macd,
    rsi,
)


class MomentumStrategy(Strategy):
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        rsi_period: int = 14,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
    ) -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    @property
    def name(self) -> str:
        return "momentum"

    @property
    def description(self) -> str:
        return (
            f"Dual EMA({self.fast_period}/{self.slow_period}) crossover "
            f"with RSI({self.rsi_period}) and MACD confirmation"
        )

    @property
    def required_history(self) -> int:
        return self.slow_period + 10

    def get_config(self) -> dict[str, Any]:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "rsi_period": self.rsi_period,
            "rsi_overbought": self.rsi_overbought,
            "rsi_oversold": self.rsi_oversold,
        }

    def generate_signals(self, prices: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        for sym in prices.columns:
            series = prices[sym].dropna()
            if len(series) < self.required_history:
                continue

            fast_ema = ema(series, self.fast_period)
            slow_ema = ema(series, self.slow_period)
            rsi_val = rsi(series, self.rsi_period)
            macd_line, _, histogram = macd(
                series, self.fast_period, self.slow_period,
            )

            latest_fast = fast_ema.iloc[-1]
            latest_slow = slow_ema.iloc[-1]
            latest_rsi = rsi_val.iloc[-1]
            latest_hist = histogram.iloc[-1]
            prev_fast = fast_ema.iloc[-2]
            prev_slow = slow_ema.iloc[-2]

            crossover_up = prev_fast <= prev_slow and latest_fast > latest_slow
            crossover_down = prev_fast >= prev_slow and latest_fast < latest_slow

            if pd.isna(latest_rsi) or pd.isna(latest_hist):
                continue

            if crossover_up and latest_rsi < self.rsi_overbought and latest_hist > 0:
                strength = min(1.0, abs(latest_hist) / (series.iloc[-1] * 0.01))
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.LONG,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={
                        "trigger": "ema_crossover_up",
                        "rsi": round(latest_rsi, 2),
                        "macd_hist": round(latest_hist, 4),
                    },
                ))
            elif crossover_down and latest_rsi > self.rsi_oversold and latest_hist < 0:
                strength = min(1.0, abs(latest_hist) / (series.iloc[-1] * 0.01))
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.SHORT,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={
                        "trigger": "ema_crossover_down",
                        "rsi": round(latest_rsi, 2),
                        "macd_hist": round(latest_hist, 4),
                    },
                ))

        return signals
