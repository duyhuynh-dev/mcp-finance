"""Strategy framework abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd


class SignalDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class Signal:
    symbol: str
    direction: SignalDirection
    strength: float  # 0.0 – 1.0
    strategy_name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        def _clean(v: Any) -> Any:
            if isinstance(v, np.bool_):
                return bool(v)
            if isinstance(v, (np.floating, np.integer)):
                return float(v)
            if isinstance(v, np.ndarray):
                return v.tolist()
            if isinstance(v, dict):
                return {k: _clean(val) for k, val in v.items()}
            if isinstance(v, (list, tuple)):
                return [_clean(i) for i in v]
            return v

        return {
            "symbol": self.symbol,
            "direction": self.direction.value,
            "strength": round(float(self.strength), 4),
            "strategy_name": self.strategy_name,
            "metadata": _clean(self.metadata),
        }


class Strategy(ABC):
    """Base class for all quant strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""

    @property
    @abstractmethod
    def required_history(self) -> int:
        """Minimum bars of price history needed."""

    @property
    def universe(self) -> list[str]:
        """Symbols this strategy trades. Override to restrict."""
        return [
            "AAPL", "MSFT", "GOOGL", "AMZN",
            "NVDA", "META", "SPY", "QQQ",
        ]

    @abstractmethod
    def generate_signals(self, prices: pd.DataFrame) -> list[Signal]:
        """
        Given a DataFrame with columns = symbols, index = timestamps,
        values = close prices, return trading signals.
        """

    def configure(self, params: dict[str, Any]) -> None:
        """Update strategy parameters at runtime."""
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def get_config(self) -> dict[str, Any]:
        """Return current parameters."""
        return {}


# ── Technical indicator helpers ──────────────────────────────────

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, middle, lower)."""
    middle = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    mean = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    return (series - mean) / std.replace(0, np.nan)
