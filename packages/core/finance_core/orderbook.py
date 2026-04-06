"""Simple order book simulation for partial fills."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class LiquidityConfig:
    base_depth: float = 100.0
    depth_variance: float = 0.3
    seed: int | None = None

    def available_liquidity(self, symbol: str) -> float:
        """Simulated available depth for a symbol at the current tick."""
        rng = random.Random(
            hash((symbol, id(self))) if self.seed is None else self.seed
        )
        factor = 1.0 + rng.uniform(-self.depth_variance, self.depth_variance)
        return max(1.0, self.base_depth * factor)


def compute_fill_quantity(
    requested: float,
    liquidity: LiquidityConfig | None = None,
    symbol: str = "",
) -> float:
    """
    Determine how many shares can be filled this tick.
    Returns min(requested, available_liquidity).
    """
    if liquidity is None:
        return requested
    avail = liquidity.available_liquidity(symbol)
    return min(requested, avail)
