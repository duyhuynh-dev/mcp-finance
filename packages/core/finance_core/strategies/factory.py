"""Construct a StrategyEngine with the default registered strategies (API + MCP)."""

from __future__ import annotations

import sqlite3

from finance_core.market import QuoteProvider
from finance_core.strategies.engine import StrategyEngine
from finance_core.strategies.mean_reversion import MeanReversionStrategy
from finance_core.strategies.ml_alpha import MLAlphaStrategy
from finance_core.strategies.momentum import MomentumStrategy
from finance_core.strategies.pairs import PairsTradingStrategy
from finance_core.strategies.portfolio_opt import OptMethod, PortfolioOptStrategy


def build_default_strategy_engine(
    conn: sqlite3.Connection,
    quotes: QuoteProvider,
    *,
    interval: float = 60.0,
) -> StrategyEngine:
    """Register all built-in quant strategies on a new engine instance."""
    engine = StrategyEngine(conn, quotes, interval=interval)
    engine.register(MomentumStrategy())
    engine.register(MeanReversionStrategy())
    engine.register(PairsTradingStrategy())
    engine.register(PortfolioOptStrategy(method=OptMethod.MAX_SHARPE))
    engine.register(PortfolioOptStrategy(method=OptMethod.RISK_PARITY))
    engine.register(PortfolioOptStrategy(method=OptMethod.MIN_VARIANCE))
    engine.register(MLAlphaStrategy())
    return engine
