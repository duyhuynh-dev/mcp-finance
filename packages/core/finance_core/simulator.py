"""Live price simulator — jitters mock prices periodically for demo purposes."""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Any

from finance_core.broadcast import event_bus
from finance_core.market import MockQuoteProvider


class PriceSimulator:
    """Background thread that randomly walks mock prices and broadcasts updates."""

    def __init__(
        self,
        provider: MockQuoteProvider,
        interval: float = 3.0,
        volatility: float = 0.003,
    ) -> None:
        self._provider = provider
        self._interval = interval
        self._volatility = volatility
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def _run(self) -> None:
        rng = random.Random()
        while self._running:
            changes: list[dict[str, Any]] = []
            for sym in self._provider.list_symbols():
                try:
                    old = self._provider.get_quote(sym).price
                except ValueError:
                    continue
                shock = rng.gauss(0, 1)
                new_price = old * math.exp(
                    -0.5 * self._volatility**2 + self._volatility * shock
                )
                new_price = round(max(new_price, 0.01), 2)
                self._provider.set_price(sym, new_price)
                changes.append({
                    "symbol": sym,
                    "old": round(old, 2),
                    "new": new_price,
                    "change_pct": round((new_price - old) / old * 100, 3),
                })

            event_bus.publish({"type": "price_tick", "prices": changes})
            time.sleep(self._interval)
