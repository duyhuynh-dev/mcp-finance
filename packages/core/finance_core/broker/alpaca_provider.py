"""Alpaca-backed QuoteProvider for real market data."""

from __future__ import annotations

import logging
import os
from datetime import UTC

from finance_core.market import Quote, QuoteProvider
from finance_core.types import utc_now

logger = logging.getLogger(__name__)


def _get_trading_client():
    from alpaca.trading.client import TradingClient

    key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    paper = os.environ.get("ALPACA_PAPER", "true").lower() in ("1", "true", "yes")
    if not key or not secret:
        raise ValueError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set"
        )
    return TradingClient(key, secret, paper=paper)


class AlpacaQuoteProvider(QuoteProvider):
    """Real-time quotes from Alpaca's market data API."""

    _POPULAR = [
        "AAPL", "AMZN", "GOOGL", "META", "MSFT",
        "NVDA", "SPY", "TSLA", "QQQ", "AMD",
    ]

    def __init__(self) -> None:
        self._client = None
        self._data_client = None

    def _ensure_data_client(self):
        if self._data_client is None:
            from alpaca.data.historical import StockHistoricalDataClient

            key = os.environ.get("ALPACA_API_KEY", "")
            secret = os.environ.get("ALPACA_SECRET_KEY", "")
            self._data_client = StockHistoricalDataClient(key, secret)
        return self._data_client

    def get_quote(self, symbol: str) -> Quote:
        sym = symbol.upper().strip()
        client = self._ensure_data_client()
        try:
            from alpaca.data.enums import DataFeed
            from alpaca.data.requests import StockLatestQuoteRequest

            request = StockLatestQuoteRequest(
                symbol_or_symbols=sym, feed=DataFeed.IEX,
            )
            quotes = client.get_stock_latest_quote(request)
            try:
                q = quotes[sym]
            except (KeyError, IndexError):
                q = None
            if q is not None:
                mid = (
                    (q.ask_price + q.bid_price) / 2
                    if q.bid_price else q.ask_price
                )
                return Quote(symbol=sym, price=float(mid), as_of=utc_now())
        except Exception:
            logger.debug("Quote API failed for %s, trying snapshot", sym)

        try:
            from alpaca.data.enums import DataFeed
            from alpaca.data.requests import StockSnapshotRequest

            request = StockSnapshotRequest(
                symbol_or_symbols=sym, feed=DataFeed.IEX,
            )
            snapshots = client.get_stock_snapshot(request)
            try:
                snap = snapshots[sym]
            except (KeyError, IndexError):
                snap = None
            if snap is not None:
                price = float(snap.latest_trade.price)
                return Quote(symbol=sym, price=price, as_of=utc_now())
        except Exception as e:
            raise ValueError(f"Alpaca quote failed for {sym}: {e}") from e

        raise ValueError(f"No Alpaca data for {sym}")

    def list_symbols(self) -> list[str]:
        return list(self._POPULAR)

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        limit: int = 100,
    ) -> list[dict]:
        """Fetch historical OHLCV bars for strategy computation."""
        from datetime import datetime, timedelta

        client = self._ensure_data_client()
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        tf = TimeFrame.Day
        sym = symbol.upper().strip()

        end = datetime.now(UTC)
        start = end - timedelta(days=int(limit * 1.8))

        from alpaca.data.enums import DataFeed

        request = StockBarsRequest(
            symbol_or_symbols=sym,
            timeframe=tf,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars_data = client.get_stock_bars(request)
        try:
            bars = bars_data[sym]
        except (KeyError, IndexError):
            bars = []
        result = [
            {
                "timestamp": str(b.timestamp),
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": float(b.volume),
            }
            for b in bars
        ]
        return result[-limit:]
