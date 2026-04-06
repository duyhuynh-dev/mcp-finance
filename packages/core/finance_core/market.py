from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from finance_core.types import utc_now


@dataclass
class Quote:
    symbol: str
    price: float
    as_of: datetime


class QuoteProvider(ABC):
    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        pass

    @abstractmethod
    def list_symbols(self) -> list[str]:
        pass


class MockQuoteProvider(QuoteProvider):
    """Deterministic mock prices for demos and tests."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices = prices or {
            "AAPL": 180.0,
            "MSFT": 380.0,
            "GOOGL": 140.0,
            "SPY": 500.0,
        }

    def get_quote(self, symbol: str) -> Quote:
        sym = symbol.upper()
        if sym not in self._prices:
            raise ValueError(f"Unknown symbol: {symbol}")
        return Quote(symbol=sym, price=float(self._prices[sym]), as_of=utc_now())

    def list_symbols(self) -> list[str]:
        return sorted(self._prices.keys())

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol.upper()] = price


class YahooChartQuoteProvider(QuoteProvider):
    """
    Last price from Yahoo Finance public chart API (no API key).
    Use FINANCE_QUOTE_BACKEND=yahoo. For CI use mock (default).
    """

    def __init__(self, timeout: float = 15.0) -> None:
        import httpx

        self._client = httpx.Client(timeout=timeout)

    def get_quote(self, symbol: str) -> Quote:
        import httpx

        sym = symbol.upper().strip()
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
            "?interval=1d&range=1d"
        )
        try:
            r = self._client.get(
                url,
                headers={"User-Agent": "finance-stack/0.1"},
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise ValueError(f"Quote fetch failed for {sym}: {e}") from e
        try:
            result = data["chart"]["result"][0]
            price = float(result["meta"]["regularMarketPrice"])
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Bad quote payload for {sym}") from e
        return Quote(symbol=sym, price=price, as_of=utc_now())

    _POPULAR = [
        "AAPL", "AMZN", "GOOGL", "META", "MSFT",
        "NVDA", "SPY", "TSLA", "QQQ", "AMD",
    ]

    def list_symbols(self) -> list[str]:
        return list(self._POPULAR)


@dataclass
class CachedQuoteProvider(QuoteProvider):
    """Wraps any provider with a TTL cache to reduce API calls."""

    _inner: QuoteProvider
    _ttl: float = 30.0
    _cache: dict[str, tuple[Quote, float]] = field(default_factory=dict)

    def get_quote(self, symbol: str) -> Quote:
        sym = symbol.upper()
        now = time.monotonic()
        cached = self._cache.get(sym)
        if cached and (now - cached[1]) < self._ttl:
            return cached[0]
        q = self._inner.get_quote(sym)
        self._cache[sym] = (q, now)
        return q

    def list_symbols(self) -> list[str]:
        return self._inner.list_symbols()

    def cache_stats(self) -> dict[str, int]:
        return {
            "cached_symbols": len(self._cache),
            "ttl_seconds": int(self._ttl),
        }
