"""REST API for the dashboard; shares FINANCE_DB_PATH with MCP portfolio server."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from finance_core.audit import list_audit
from finance_core.ledger import Ledger, reset_demo_db
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.quote_factory import create_quote_provider
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = str(ROOT / "data" / "finance.db")

_ledger: Ledger | None = None


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        path = os.environ.get("FINANCE_DB_PATH", DEFAULT_DB)
        _ledger = Ledger.open(path, quotes=create_quote_provider())
        _ledger.set_policy(PolicyEngine(PolicyRules.default()))
    return _ledger


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="Finance Stack API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(
        ","
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/portfolio")
def portfolio(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    s = lg.portfolio_state()
    pr = lg.policy_engine.rules
    return {
        "cash": s.cash,
        "equity": lg.estimated_equity(),
        "trading_enabled": s.trading_enabled,
        "positions": {k: {"quantity": v.quantity} for k, v in s.positions.items()},
        "rules": {
            "version": pr.version,
            "max_shares_per_symbol": pr.max_shares_per_symbol,
            "max_order_notional": pr.max_order_notional,
            "fee_bps": pr.fee_bps,
        },
    }


@app.get("/api/orders")
def orders(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 50) -> dict:
    rows = lg.list_orders(limit=min(limit, 200))
    return {
        "orders": [
            {
                "id": o.id,
                "client_order_id": o.client_order_id,
                "symbol": o.symbol,
                "side": o.side.value,
                "quantity": o.quantity,
                "status": o.status.value,
                "rejection_reason": o.rejection_reason.value if o.rejection_reason else None,
                "order_kind": o.order_kind.value,
                "limit_price": o.limit_price,
                "created_at": o.created_at.isoformat(),
            }
            for o in rows
        ]
    }


@app.get("/api/fills")
def fills(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 50) -> dict:
    rows = lg.list_fills(limit=min(limit, 200))
    return {
        "fills": [
            {
                "id": f.id,
                "order_id": f.order_id,
                "symbol": f.symbol,
                "side": f.side.value,
                "quantity": f.quantity,
                "price": f.price,
                "fee": f.fee,
                "filled_at": f.filled_at.isoformat(),
            }
            for f in rows
        ]
    }


@app.get("/api/equity-series")
def equity_series(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 200) -> dict:
    return {"points": lg.equity_series(limit=min(limit, 500))}


@app.get("/api/audit")
def audit(
    lg: Annotated[Ledger, Depends(get_ledger)],
    limit: int = 80,
    offset: int = 0,
) -> dict:
    rows = list_audit(lg.conn, limit=min(limit, 200), offset=offset)
    return {"events": rows}


class DepositBody(BaseModel):
    amount: float = Field(gt=0)


@app.post("/api/deposit")
def deposit(lg: Annotated[Ledger, Depends(get_ledger)], body: DepositBody) -> dict:
    cash = lg.deposit(body.amount, actor="dashboard")
    return {"cash": cash}


class TradingBody(BaseModel):
    enabled: bool


@app.post("/api/trading-enabled")
def trading_enabled(lg: Annotated[Ledger, Depends(get_ledger)], body: TradingBody) -> dict:
    lg.set_trading_enabled(body.enabled, actor="dashboard")
    return {"trading_enabled": body.enabled}


@app.post("/api/reset-demo")
def reset_demo(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    reset_demo_db(lg.conn)
    return {"ok": True}


@app.post("/api/cancel-order/{order_id}")
def cancel_order_endpoint(
    lg: Annotated[Ledger, Depends(get_ledger)],
    order_id: int,
) -> dict:
    return lg.cancel_order(order_id, actor="dashboard")


def create_app() -> FastAPI:
    return app
