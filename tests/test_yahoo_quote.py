from __future__ import annotations

from unittest.mock import MagicMock, patch

from finance_core.market import YahooChartQuoteProvider


def test_yahoo_chart_parses_regular_market_price() -> None:
    sample = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 123.45,
                    }
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = sample
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    with patch("httpx.Client", return_value=mock_client):
        p = YahooChartQuoteProvider()
        q = p.get_quote("AAPL")

    assert q.symbol == "AAPL"
    assert q.price == 123.45
