#!/usr/bin/env python3
"""MCP server: mock market quotes (read-only)."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "packages", "core"))

from finance_core.quote_factory import create_quote_provider
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("finance-market")

_quotes = create_quote_provider()


@mcp.tool()
def get_quote(symbol: str) -> dict:
    """Return last price and timestamp for a symbol."""
    q = _quotes.get_quote(symbol.strip())
    return {
        "symbol": q.symbol,
        "price": q.price,
        "as_of": q.as_of.isoformat(),
    }


@mcp.tool()
def list_symbols() -> list[str]:
    """List symbols available in the market universe."""
    return _quotes.list_symbols()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
