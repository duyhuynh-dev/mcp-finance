"""Order executor abstraction — internal (simulated) vs external (broker)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class ExecutionMode(StrEnum):
    INTERNAL = "internal"
    ALPACA_PAPER = "alpaca_paper"


@dataclass
class ExecutionResult:
    filled: bool
    fill_price: float
    fill_quantity: float
    remaining_quantity: float
    broker_order_id: str | None = None
    fees: float = 0.0
    metadata: dict = field(default_factory=dict)


class OrderExecutor(ABC):
    """Routes order execution to internal simulation or external broker."""

    @property
    @abstractmethod
    def mode(self) -> ExecutionMode: ...

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: float | None = None,
        time_in_force: str = "day",
    ) -> ExecutionResult: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool: ...

    @abstractmethod
    def get_account_info(self) -> dict: ...


class InternalExecutor(OrderExecutor):
    """Default executor — fill simulation handled by Ledger itself."""

    @property
    def mode(self) -> ExecutionMode:
        return ExecutionMode.INTERNAL

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: float | None = None,
        time_in_force: str = "day",
    ) -> ExecutionResult:
        raise NotImplementedError(
            "InternalExecutor delegates to Ledger's built-in fill logic"
        )

    def cancel_order(self, broker_order_id: str) -> bool:
        return False

    def get_account_info(self) -> dict:
        return {"mode": self.mode.value, "connected": True}
