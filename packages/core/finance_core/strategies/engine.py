"""Strategy engine — orchestrates registered strategies on a schedule."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any

import pandas as pd

from finance_core.broadcast import event_bus
from finance_core.market import QuoteProvider
from finance_core.strategies.base import Signal, Strategy
from finance_core.types import utc_now

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Runs strategies on a schedule and routes signals to the ledger."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        quotes: QuoteProvider,
        *,
        interval: float = 60.0,
    ) -> None:
        self._conn = conn
        self._quotes = quotes
        self._interval = interval
        self._strategies: dict[str, Strategy] = {}
        self._active: set[str] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def register(self, strategy: Strategy) -> None:
        with self._lock:
            self._strategies[strategy.name] = strategy

    def activate(self, name: str) -> bool:
        if name not in self._strategies:
            return False
        with self._lock:
            self._active.add(name)
        return True

    def deactivate(self, name: str) -> bool:
        with self._lock:
            self._active.discard(name)
        return True

    def list_strategies(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": s.name,
                    "description": s.description,
                    "active": s.name in self._active,
                    "required_history": s.required_history,
                    "universe": s.universe,
                    "config": s.get_config(),
                }
                for s in self._strategies.values()
            ]

    def get_strategy(self, name: str) -> Strategy | None:
        return self._strategies.get(name)

    def _fetch_price_history(
        self, symbols: list[str], bars: int,
    ) -> pd.DataFrame:
        """Build a price DataFrame from stored history, broker bars, or quotes."""
        rows = self._conn.execute(
            """
            SELECT symbol, price, recorded_at
            FROM price_history
            WHERE symbol IN ({})
            ORDER BY recorded_at DESC
            LIMIT ?
            """.format(",".join("?" * len(symbols))),
            (*symbols, bars * len(symbols)),
        ).fetchall()

        if rows and len(rows) >= bars:
            data: dict[str, list[float]] = {s: [] for s in symbols}
            timestamps: list[str] = []
            seen_ts: set[str] = set()
            for r in reversed(rows):
                ts = r["recorded_at"]
                if ts not in seen_ts:
                    seen_ts.add(ts)
                    timestamps.append(ts)
                data.setdefault(r["symbol"], []).append(
                    float(r["price"]),
                )

            max_len = max(
                len(v) for v in data.values()
            ) if data else 0
            for s in symbols:
                while len(data[s]) < max_len:
                    data[s].insert(0, data[s][0] if data[s] else 0)

            df = pd.DataFrame(data)
            if timestamps and len(timestamps) == len(df):
                df.index = pd.to_datetime(timestamps)
            return df

        df = self._fetch_broker_bars(symbols, bars)
        if df is not None and not df.empty:
            return df

        prices: dict[str, float] = {}
        for sym in symbols:
            try:
                q = self._quotes.get_quote(sym)
                prices[sym] = q.price
            except ValueError:
                continue
        if not prices:
            return pd.DataFrame()
        return pd.DataFrame([prices])

    def _fetch_broker_bars(
        self, symbols: list[str], bars: int,
    ) -> pd.DataFrame | None:
        """Pull historical daily bars from broker if available."""
        from finance_core.market import CachedQuoteProvider

        provider = self._quotes
        if isinstance(provider, CachedQuoteProvider):
            provider = provider._inner

        if not hasattr(provider, "get_historical_bars"):
            return None

        all_data: dict[str, list[float]] = {}
        for sym in symbols:
            try:
                bar_list = provider.get_historical_bars(
                    sym, timeframe="1Day", limit=bars,
                )
                if bar_list:
                    all_data[sym] = [b["close"] for b in bar_list]
            except Exception:
                logger.debug("Failed to fetch bars for %s", sym)
                continue

        if not all_data:
            return None

        max_len = max(len(v) for v in all_data.values())
        for sym in list(all_data.keys()):
            while len(all_data[sym]) < max_len:
                all_data[sym].insert(0, all_data[sym][0])

        return pd.DataFrame(all_data)

    def run_once(self) -> list[Signal]:
        """Execute all active strategies once, return signals."""
        all_signals: list[Signal] = []
        with self._lock:
            active_names = list(self._active)

        for name in active_names:
            strat = self._strategies.get(name)
            if not strat:
                continue
            try:
                df = self._fetch_price_history(
                    strat.universe, strat.required_history,
                )
                if df.empty or len(df) < 2:
                    continue
                signals = strat.generate_signals(df)
                all_signals.extend(signals)
                self._persist_signals(signals)
            except Exception:
                logger.exception("Strategy %s failed", name)

        return all_signals

    def _persist_signals(self, signals: list[Signal]) -> None:
        ts = utc_now().isoformat()
        for sig in signals:
            clean = sig.to_dict()
            self._conn.execute(
                """INSERT INTO strategy_signals
                   (strategy_name, symbol, direction, strength, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    sig.strategy_name, sig.symbol,
                    sig.direction.value, float(sig.strength),
                    json.dumps(clean["metadata"]), ts,
                ),
            )
        self._conn.commit()
        for sig in signals:
            event_bus.publish({
                "type": "strategy_signal",
                **sig.to_dict(),
            })

    def record_price(self, symbol: str, price: float) -> None:
        """Store a price tick for strategy lookback."""
        ts = utc_now().isoformat()
        self._conn.execute(
            "INSERT INTO price_history (symbol, price, volume, recorded_at) "
            "VALUES (?, ?, NULL, ?)",
            (symbol.upper(), price, ts),
        )
        self._conn.commit()

    def recent_signals(
        self, strategy_name: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        if strategy_name:
            rows = self._conn.execute(
                """SELECT * FROM strategy_signals
                   WHERE strategy_name = ?
                   ORDER BY id DESC LIMIT ?""",
                (strategy_name, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM strategy_signals ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "strategy_name": r["strategy_name"],
                "symbol": r["symbol"],
                "direction": r["direction"],
                "strength": float(r["strength"]),
                "metadata": json.loads(r["metadata_json"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ── background runner ──────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("StrategyEngine started (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("StrategyEngine stopped")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("StrategyEngine tick failed")
            self._stop.wait(self._interval)
