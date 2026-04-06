"""Mean reversion strategy — Bollinger Bands + z-score."""

from __future__ import annotations

from typing import Any

import pandas as pd

from finance_core.strategies.base import (
    Signal,
    SignalDirection,
    Strategy,
    bollinger_bands,
    zscore,
)


class MeanReversionStrategy(Strategy):
    def __init__(
        self,
        window: int = 20,
        num_std: float = 2.0,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
    ) -> None:
        self.window = window
        self.num_std = num_std
        self.entry_z = entry_z
        self.exit_z = exit_z

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def description(self) -> str:
        return (
            f"Bollinger Bands({self.window}, {self.num_std}σ) "
            f"mean reversion at z={self.entry_z}"
        )

    @property
    def required_history(self) -> int:
        return self.window + 5

    def get_config(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "num_std": self.num_std,
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
        }

    def generate_signals(self, prices: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        for sym in prices.columns:
            series = prices[sym].dropna()
            if len(series) < self.required_history:
                continue

            upper, middle, lower = bollinger_bands(
                series, self.window, self.num_std,
            )
            z = zscore(series, self.window)

            latest_z = z.iloc[-1]
            latest_price = series.iloc[-1]
            latest_upper = upper.iloc[-1]
            latest_lower = lower.iloc[-1]
            latest_mid = middle.iloc[-1]

            if pd.isna(latest_z):
                continue

            band_width = latest_upper - latest_lower
            if band_width < 1e-9:
                continue

            if latest_z < -self.entry_z:
                distance = abs(latest_z) - self.entry_z
                strength = min(1.0, 0.5 + distance * 0.25)
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.LONG,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={
                        "trigger": "below_lower_band",
                        "z_score": round(latest_z, 4),
                        "price": round(latest_price, 2),
                        "lower_band": round(latest_lower, 2),
                        "middle": round(latest_mid, 2),
                        "band_width_pct": round(
                            band_width / latest_mid * 100, 2,
                        ),
                    },
                ))
            elif latest_z > self.entry_z:
                distance = latest_z - self.entry_z
                strength = min(1.0, 0.5 + distance * 0.25)
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.SHORT,
                    strength=round(strength, 4),
                    strategy_name=self.name,
                    metadata={
                        "trigger": "above_upper_band",
                        "z_score": round(latest_z, 4),
                        "price": round(latest_price, 2),
                        "upper_band": round(latest_upper, 2),
                        "middle": round(latest_mid, 2),
                        "band_width_pct": round(
                            band_width / latest_mid * 100, 2,
                        ),
                    },
                ))
            elif abs(latest_z) < self.exit_z:
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.FLAT,
                    strength=0.3,
                    strategy_name=self.name,
                    metadata={
                        "trigger": "revert_to_mean",
                        "z_score": round(latest_z, 4),
                    },
                ))

        return signals
