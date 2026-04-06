"""Select quote provider from env (mock for CI/tests, Yahoo/Alpaca for demos)."""

from __future__ import annotations

import os

from finance_core.market import (
    CachedQuoteProvider,
    MockQuoteProvider,
    QuoteProvider,
    YahooChartQuoteProvider,
)


def create_quote_provider() -> QuoteProvider:
    """
    FINANCE_QUOTE_BACKEND:
      - mock (default): deterministic prices, no network
      - yahoo: live last price via Yahoo chart API (no API key), cached 30s
      - alpaca: real-time quotes via Alpaca market data API, cached 15s
    """
    backend = os.environ.get("FINANCE_QUOTE_BACKEND", "mock").strip().lower()
    ttl = float(os.environ.get("QUOTE_CACHE_TTL", "30"))
    if backend == "yahoo":
        return CachedQuoteProvider(
            _inner=YahooChartQuoteProvider(), _ttl=ttl,
        )
    if backend == "alpaca":
        from finance_core.broker.alpaca_provider import AlpacaQuoteProvider

        return CachedQuoteProvider(
            _inner=AlpacaQuoteProvider(), _ttl=min(ttl, 15),
        )
    return MockQuoteProvider()
