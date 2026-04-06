"""Portfolio optimization — Markowitz, risk parity, minimum variance."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from finance_core.strategies.base import Signal, SignalDirection, Strategy


class OptMethod(StrEnum):
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    RISK_PARITY = "risk_parity"


def _max_sharpe_weights(
    returns: pd.DataFrame, risk_free: float = 0.0,
) -> np.ndarray:
    """Optimize for maximum Sharpe ratio."""
    n = len(returns.columns)
    mu = returns.mean().values * 252
    cov = returns.cov().values * 252
    w0 = np.ones(n) / n

    def neg_sharpe(w):
        port_ret = w @ mu
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol < 1e-10:
            return 0
        return -(port_ret - risk_free) / port_vol

    bounds = [(0.0, 1.0)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    result = minimize(
        neg_sharpe, w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
    )
    return result.x if result.success else w0


def _min_variance_weights(returns: pd.DataFrame) -> np.ndarray:
    """Global minimum variance portfolio."""
    n = len(returns.columns)
    cov = returns.cov().values * 252
    w0 = np.ones(n) / n

    def port_var(w):
        return w @ cov @ w

    bounds = [(0.0, 1.0)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    result = minimize(
        port_var, w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
    )
    return result.x if result.success else w0


def _risk_parity_weights(returns: pd.DataFrame) -> np.ndarray:
    """Equalize marginal risk contribution across assets."""
    n = len(returns.columns)
    cov = returns.cov().values * 252
    w0 = np.ones(n) / n

    def risk_budget_obj(w):
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol < 1e-10:
            return 0
        mrc = cov @ w / port_vol
        rc = w * mrc
        target = port_vol / n
        return np.sum((rc - target) ** 2)

    bounds = [(0.01, 1.0)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    result = minimize(
        risk_budget_obj, w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
    )
    return result.x if result.success else w0


class PortfolioOptStrategy(Strategy):
    def __init__(
        self,
        method: OptMethod = OptMethod.MAX_SHARPE,
        risk_free: float = 0.04,
        rebalance_threshold: float = 0.05,
    ) -> None:
        self.method = method
        self.risk_free = risk_free
        self.rebalance_threshold = rebalance_threshold
        self._current_weights: dict[str, float] = {}

    @property
    def name(self) -> str:
        return f"portfolio_opt_{self.method.value}"

    @property
    def description(self) -> str:
        labels = {
            OptMethod.MAX_SHARPE: "Maximum Sharpe Ratio",
            OptMethod.MIN_VARIANCE: "Minimum Variance",
            OptMethod.RISK_PARITY: "Risk Parity",
        }
        return f"Portfolio optimization — {labels.get(self.method, self.method)}"

    @property
    def required_history(self) -> int:
        return 60

    def get_config(self) -> dict[str, Any]:
        return {
            "method": self.method.value,
            "risk_free": self.risk_free,
            "rebalance_threshold": self.rebalance_threshold,
            "current_weights": self._current_weights,
        }

    def generate_signals(self, prices: pd.DataFrame) -> list[Signal]:
        if len(prices) < 20 or len(prices.columns) < 2:
            return []

        returns = prices.pct_change().dropna()
        if len(returns) < 10:
            return []

        valid_cols = [c for c in returns.columns if returns[c].std() > 1e-10]
        if len(valid_cols) < 2:
            return []
        returns = returns[valid_cols]

        if self.method == OptMethod.MAX_SHARPE:
            weights = _max_sharpe_weights(returns, self.risk_free)
        elif self.method == OptMethod.MIN_VARIANCE:
            weights = _min_variance_weights(returns)
        else:
            weights = _risk_parity_weights(returns)

        target_weights = {
            sym: round(float(w), 4)
            for sym, w in zip(valid_cols, weights)
        }

        port_ret = (returns.mean() * 252) @ weights
        port_vol = np.sqrt(weights @ (returns.cov().values * 252) @ weights)
        sharpe = (port_ret - self.risk_free) / port_vol if port_vol > 0 else 0

        signals: list[Signal] = []
        for sym, target_w in target_weights.items():
            current_w = self._current_weights.get(sym, 0.0)
            delta = target_w - current_w

            if abs(delta) < self.rebalance_threshold:
                continue

            direction = SignalDirection.LONG if delta > 0 else SignalDirection.SHORT
            strength = min(1.0, abs(delta) * 2)

            signals.append(Signal(
                symbol=sym,
                direction=direction,
                strength=round(strength, 4),
                strategy_name=self.name,
                metadata={
                    "target_weight": target_w,
                    "current_weight": round(current_w, 4),
                    "delta": round(delta, 4),
                    "method": self.method.value,
                    "portfolio_sharpe": round(sharpe, 4),
                    "portfolio_vol": round(port_vol, 4),
                    "portfolio_return": round(port_ret, 4),
                    "all_weights": target_weights,
                },
            ))

        self._current_weights = target_weights
        return signals
