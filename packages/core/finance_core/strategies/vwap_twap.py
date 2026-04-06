"""VWAP / TWAP execution algorithms — smart order slicing."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from finance_core.types import utc_now


@dataclass
class SliceOrder:
    """A single child order in a VWAP/TWAP execution plan."""
    sequence: int
    quantity: float
    target_time: str
    weight: float
    executed: bool = False
    fill_price: float | None = None


@dataclass
class ExecutionPlan:
    """Full plan for slicing a parent order."""
    parent_symbol: str
    parent_side: str
    total_quantity: float
    algorithm: str
    slices: list[SliceOrder] = field(default_factory=list)
    benchmark_price: float = 0.0
    avg_fill_price: float = 0.0
    slippage_bps: float = 0.0
    implementation_shortfall: float = 0.0
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        filled = [s for s in self.slices if s.executed]
        if filled:
            total_notional = sum(s.quantity * (s.fill_price or 0) for s in filled)
            total_qty = sum(s.quantity for s in filled)
            self.avg_fill_price = total_notional / total_qty if total_qty else 0
            if self.benchmark_price > 0:
                self.slippage_bps = (
                    (self.avg_fill_price - self.benchmark_price)
                    / self.benchmark_price * 10_000
                )
                self.implementation_shortfall = (
                    (self.avg_fill_price - self.benchmark_price)
                    * total_qty
                )

        return {
            "symbol": self.parent_symbol,
            "side": self.parent_side,
            "total_quantity": self.total_quantity,
            "algorithm": self.algorithm,
            "benchmark_price": round(self.benchmark_price, 4),
            "avg_fill_price": round(self.avg_fill_price, 4),
            "slippage_bps": round(self.slippage_bps, 2),
            "implementation_shortfall": round(self.implementation_shortfall, 2),
            "completed": self.completed,
            "slices_total": len(self.slices),
            "slices_filled": sum(1 for s in self.slices if s.executed),
            "slices": [
                {
                    "seq": s.sequence,
                    "qty": s.quantity,
                    "weight": round(s.weight, 4),
                    "target_time": s.target_time,
                    "executed": s.executed,
                    "fill_price": s.fill_price,
                }
                for s in self.slices
            ],
        }


class TWAPExecutor:
    """Time-Weighted Average Price — slices order evenly over time."""

    def __init__(self, num_slices: int = 10, interval_seconds: int = 60) -> None:
        self.num_slices = num_slices
        self.interval_seconds = interval_seconds

    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: float,
        benchmark_price: float = 0.0,
    ) -> ExecutionPlan:
        qty_per_slice = quantity / self.num_slices
        remainder = quantity - qty_per_slice * self.num_slices
        weight = 1.0 / self.num_slices

        slices: list[SliceOrder] = []
        now = utc_now()
        for i in range(self.num_slices):
            q = qty_per_slice + (remainder if i == self.num_slices - 1 else 0)
            import datetime
            target = now + datetime.timedelta(seconds=self.interval_seconds * i)
            slices.append(SliceOrder(
                sequence=i,
                quantity=round(q, 6),
                target_time=target.isoformat(),
                weight=round(weight, 6),
            ))

        return ExecutionPlan(
            parent_symbol=symbol.upper(),
            parent_side=side.upper(),
            total_quantity=quantity,
            algorithm="TWAP",
            slices=slices,
            benchmark_price=benchmark_price,
        )


class VWAPExecutor:
    """Volume-Weighted Average Price — slices proportional to volume profile."""

    def __init__(
        self,
        num_slices: int = 10,
        interval_seconds: int = 60,
    ) -> None:
        self.num_slices = num_slices
        self.interval_seconds = interval_seconds

    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: float,
        volume_profile: list[float] | None = None,
        benchmark_price: float = 0.0,
    ) -> ExecutionPlan:
        if volume_profile and len(volume_profile) >= self.num_slices:
            profile = volume_profile[: self.num_slices]
        else:
            profile = self._synthetic_profile(self.num_slices)

        total_vol = sum(profile)
        if total_vol > 0:
            weights = [v / total_vol for v in profile]
        else:
            weights = [1 / self.num_slices] * self.num_slices

        slices: list[SliceOrder] = []
        now = utc_now()
        allocated = 0.0
        for i, w in enumerate(weights):
            q = round(quantity * w, 6)
            if i == len(weights) - 1:
                q = round(quantity - allocated, 6)
            allocated += q
            import datetime
            target = now + datetime.timedelta(seconds=self.interval_seconds * i)
            slices.append(SliceOrder(
                sequence=i,
                quantity=q,
                target_time=target.isoformat(),
                weight=round(w, 6),
            ))

        return ExecutionPlan(
            parent_symbol=symbol.upper(),
            parent_side=side.upper(),
            total_quantity=quantity,
            algorithm="VWAP",
            slices=slices,
            benchmark_price=benchmark_price,
        )

    @staticmethod
    def _synthetic_profile(n: int) -> list[float]:
        """U-shaped intraday volume profile (higher at open/close)."""
        profile = []
        for i in range(n):
            t = i / max(n - 1, 1)
            vol = 1.0 + 2.0 * math.exp(-10 * (t - 0.0) ** 2) + 1.5 * math.exp(-10 * (t - 1.0) ** 2)
            profile.append(vol)
        return profile
