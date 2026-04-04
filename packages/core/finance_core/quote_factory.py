"""Select quote provider from env (mock for CI/tests, Yahoo for local demos)."""

from __future__ import annotations

import os

from finance_core.market import MockQuoteProvider, QuoteProvider, YahooChartQuoteProvider


def create_quote_provider() -> QuoteProvider:
    """
    FINANCE_QUOTE_BACKEND:
      - mock (default): deterministic prices, no network
      - yahoo: live last price via Yahoo chart API (no API key)
    """
    backend = os.environ.get("FINANCE_QUOTE_BACKEND", "mock").strip().lower()
    if backend == "yahoo":
        return YahooChartQuoteProvider()
    return MockQuoteProvider()
