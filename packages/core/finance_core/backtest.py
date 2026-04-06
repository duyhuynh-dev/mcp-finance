"""Backtesting framework: replay synthetic or historical price data through the ledger."""

from __future__ import annotations

import math
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules, load_rules_from_dict
from finance_core.risk import compute_risk_metrics
from finance_core.types import OrderSide


@dataclass
class PriceTick:
    symbol: str
    price: float
    step: int


@dataclass
class StrategyRule:
    """Simple rule: buy_below or sell_above a price threshold."""

    rule_type: str
    symbol: str
    threshold: float
    quantity: float

    @staticmethod
    def from_dict(d: dict[str, Any]) -> StrategyRule:
        return StrategyRule(
            rule_type=d["type"],
            symbol=d["symbol"].upper(),
            threshold=float(d["threshold"]),
            quantity=float(d["quantity"]),
        )


@dataclass
class BacktestConfig:
    name: str
    initial_cash: float
    rules: list[StrategyRule]
    symbols: list[str]
    steps: int = 100
    seed: int = 42
    drift: float = 0.0005
    volatility: float = 0.02
    start_prices: dict[str, float] = field(default_factory=dict)
    policy: dict[str, Any] | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> BacktestConfig:
        rules = [StrategyRule.from_dict(r) for r in d.get("rules", [])]
        symbols = list({r.symbol for r in rules})
        return BacktestConfig(
            name=d.get("name", "unnamed"),
            initial_cash=float(d.get("initial_cash", 100_000)),
            rules=rules,
            symbols=symbols,
            steps=int(d.get("steps", 100)),
            seed=int(d.get("seed", 42)),
            drift=float(d.get("drift", 0.0005)),
            volatility=float(d.get("volatility", 0.02)),
            start_prices={
                k.upper(): float(v)
                for k, v in (d.get("start_prices") or {}).items()
            },
            policy=d.get("policy"),
        )


@dataclass
class BacktestResult:
    name: str
    steps: int
    final_equity: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate: float
    profit_factor: float
    equity_curve: list[float]
    price_history: dict[str, list[float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "steps": self.steps,
            "final_equity": round(self.final_equity, 2),
            "total_return_pct": round(self.total_return_pct, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "equity_curve": [round(e, 2) for e in self.equity_curve],
            "price_history": {
                k: [round(p, 2) for p in v] for k, v in self.price_history.items()
            },
        }


def generate_prices(
    symbols: list[str],
    steps: int,
    start_prices: dict[str, float] | None = None,
    drift: float = 0.0005,
    volatility: float = 0.02,
    seed: int = 42,
) -> list[PriceTick]:
    """Generate geometric Brownian motion price paths."""
    rng = random.Random(seed)
    defaults = {"AAPL": 180.0, "MSFT": 380.0, "GOOGL": 140.0, "SPY": 500.0}
    sp = start_prices or {}
    prices: dict[str, float] = {}
    for sym in symbols:
        prices[sym] = sp.get(sym, defaults.get(sym, 100.0))

    ticks: list[PriceTick] = []
    for step in range(steps):
        for sym in symbols:
            ticks.append(PriceTick(symbol=sym, price=prices[sym], step=step))
            shock = rng.gauss(0, 1)
            prices[sym] *= math.exp(drift - 0.5 * volatility**2 + volatility * shock)
            prices[sym] = max(prices[sym], 0.01)
    return ticks


def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Execute a backtest: create temp ledger, replay prices, evaluate strategy."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        init_prices = {}
        for sym in config.symbols:
            init_prices[sym] = config.start_prices.get(sym, 100.0)

        quotes = MockQuoteProvider(dict(init_prices))
        if config.policy:
            policy = PolicyEngine(load_rules_from_dict(config.policy))
        else:
            policy = PolicyEngine(PolicyRules.default())

        lg = Ledger.open(db_path, quotes=quotes, policy=policy)
        lg.deposit(config.initial_cash, actor="backtest")

        ticks = generate_prices(
            config.symbols,
            config.steps,
            start_prices=config.start_prices or None,
            drift=config.drift,
            volatility=config.volatility,
            seed=config.seed,
        )

        price_history: dict[str, list[float]] = {s: [] for s in config.symbols}
        order_seq = 0
        ticks_by_step: dict[int, list[PriceTick]] = {}
        for t in ticks:
            ticks_by_step.setdefault(t.step, []).append(t)

        for step in range(config.steps):
            step_ticks = ticks_by_step.get(step, [])
            for t in step_ticks:
                quotes.set_price(t.symbol, t.price)
                price_history[t.symbol].append(t.price)

            for rule in config.rules:
                try:
                    current = quotes.get_quote(rule.symbol).price
                except ValueError:
                    continue

                should_trade = False
                side = OrderSide.BUY
                if rule.rule_type == "buy_below" and current < rule.threshold:
                    should_trade = True
                    side = OrderSide.BUY
                elif rule.rule_type == "sell_above" and current > rule.threshold:
                    should_trade = True
                    side = OrderSide.SELL

                if should_trade:
                    order_seq += 1
                    lg.place_order(
                        f"bt-{config.seed}-{order_seq}",
                        rule.symbol,
                        side,
                        rule.quantity,
                        actor="backtest",
                    )

        risk = compute_risk_metrics(lg.conn)
        eq_curve = risk.equity_curve if risk.equity_curve else [config.initial_cash]
        final_eq = eq_curve[-1] if eq_curve else config.initial_cash

        return BacktestResult(
            name=config.name,
            steps=config.steps,
            final_equity=final_eq,
            total_return_pct=risk.total_return_pct,
            sharpe_ratio=risk.sharpe_ratio,
            max_drawdown_pct=risk.max_drawdown_pct,
            total_trades=risk.total_trades,
            win_rate=risk.win_rate,
            profit_factor=risk.profit_factor,
            equity_curve=eq_curve,
            price_history=price_history,
        )
    finally:
        Path(db_path).unlink(missing_ok=True)
