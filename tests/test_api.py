from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from finance_core.broker.base import ExecutionResult
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules

from api.main import app, get_ledger


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "api.db"
        os.environ["FINANCE_DB_PATH"] = str(db)
        app.dependency_overrides.clear()
        quotes = MockQuoteProvider({"AAPL": 180.0, "MSFT": 380.0})
        policy = PolicyEngine(
            PolicyRules(
                version="t",
                max_shares_per_symbol=1000.0,
                max_order_notional=50_000.0,
                fee_bps=10.0,
                slippage_bps=5.0,
            )
        )
        ledger = Ledger.open(str(db), quotes=quotes, policy=policy)

        def _override():
            return ledger

        app.dependency_overrides[get_ledger] = _override
        with TestClient(app) as tc:
            yield tc
        app.dependency_overrides.clear()


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["strategy_engine"]["initialized"] is True
    assert data["strategy_engine"]["running"] is False


def test_ml_alpha_diagnostics_endpoint(client: TestClient):
    r = client.get("/api/strategies/ml_alpha/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"] == "ml_alpha"
    assert "methodology" in body
    assert body["methodology"]["split"] == "time_ordered_80_20"


def test_momentum_diagnostics_not_available(client: TestClient):
    r = client.get("/api/strategies/momentum/diagnostics")
    assert r.status_code == 404


def test_place_order_broker_mode_mirrors_fill(client: TestClient, monkeypatch):
    from finance_core.broker.alpaca_executor import AlpacaOrderExecutor

    import api.main as main_mod

    monkeypatch.setenv("BROKER_EXECUTION_MODE", "alpaca_paper")

    def _fake_submit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: float | None = None,
        time_in_force: str = "day",
    ) -> ExecutionResult:
        _ = (self, symbol, side, order_type, limit_price, time_in_force)
        return ExecutionResult(
            filled=True,
            fill_price=180.0,
            fill_quantity=quantity,
            remaining_quantity=0.0,
            broker_order_id="paper-123",
            fees=0.0,
        )

    monkeypatch.setattr(AlpacaOrderExecutor, "submit_order", _fake_submit)
    client.post("/api/deposit", json={"amount": 10_000.0})
    r = client.post(
        "/api/place-order",
        json={
            "client_order_id": "broker-mirror-1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10,
            "order_kind": "MARKET",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["status"] == "FILLED"
    assert body["broker_mode"] == "alpaca_paper"
    assert body["broker_order_id"] == "paper-123"

    monkeypatch.setenv("BROKER_EXECUTION_MODE", "internal")
    main_mod.os.environ["BROKER_EXECUTION_MODE"] = "internal"


def test_deposit_and_portfolio(client: TestClient):
    r = client.post("/api/deposit", json={"amount": 1000.0})
    assert r.status_code == 200
    p = client.get("/api/portfolio")
    assert p.status_code == 200
    data = p.json()
    assert data["cash"] == 1000.0
    assert "total_realized_pnl" in data
    assert "total_unrealized_pnl" in data
    assert "rules" in data
    assert "slippage_bps" in data["rules"]


def test_execution_events_and_replay(client: TestClient):
    import api.main as main_mod

    main_mod.os.environ["BROKER_EXECUTION_MODE"] = "internal"
    client.post("/api/deposit", json={"amount": 10_000.0})
    client.post(
        "/api/place-order",
        json={
            "client_order_id": "evt-1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 2,
            "order_kind": "MARKET",
        },
    )
    ev = client.get("/api/execution-events?limit=20")
    assert ev.status_code == 200
    events = ev.json()["events"]
    assert len(events) >= 1
    assert any(e["event_type"] in ("order_filled", "order_opened") for e in events)

    rp = client.get("/api/execution-events/replay")
    assert rp.status_code == 200
    body = rp.json()
    assert "total_events" in body
    assert body["total_events"] >= 1


def test_place_order_buy(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    r = client.post(
        "/api/place-order",
        json={
            "client_order_id": "t1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["status"] == "FILLED"


def test_place_order_sell(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    client.post(
        "/api/place-order",
        json={"client_order_id": "b1", "symbol": "AAPL", "side": "BUY", "quantity": 10},
    )
    r = client.post(
        "/api/place-order",
        json={"client_order_id": "s1", "symbol": "AAPL", "side": "SELL", "quantity": 10},
    )
    data = r.json()
    assert data["success"] is True


def test_place_order_limit(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    r = client.post(
        "/api/place-order",
        json={
            "client_order_id": "lim1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 5,
            "order_kind": "LIMIT",
            "limit_price": 150.0,
        },
    )
    data = r.json()
    assert data["success"] is True
    assert data["status"] == "PENDING"


def test_cancel_order(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    r = client.post(
        "/api/place-order",
        json={
            "client_order_id": "lim2",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 5,
            "order_kind": "LIMIT",
            "limit_price": 100.0,
        },
    )
    oid = r.json()["order_id"]
    cr = client.post(f"/api/cancel-order/{oid}")
    assert cr.status_code == 200
    assert cr.json()["ok"] is True


def test_orders_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    client.post(
        "/api/place-order",
        json={"client_order_id": "o1", "symbol": "AAPL", "side": "BUY", "quantity": 5},
    )
    r = client.get("/api/orders")
    assert r.status_code == 200
    orders = r.json()["orders"]
    assert len(orders) >= 1
    o = orders[0]
    assert "order_kind" in o
    assert "limit_price" in o


def test_fills_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    client.post(
        "/api/place-order",
        json={"client_order_id": "f1", "symbol": "AAPL", "side": "BUY", "quantity": 5},
    )
    r = client.get("/api/fills")
    assert r.status_code == 200
    fills = r.json()["fills"]
    assert len(fills) >= 1
    f = fills[0]
    assert "fee" in f
    assert "realized_pnl" in f


def test_equity_series_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 1000.0})
    r = client.get("/api/equity-series")
    assert r.status_code == 200
    assert "points" in r.json()


def test_audit_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 1000.0})
    r = client.get("/api/audit")
    assert r.status_code == 200
    assert "events" in r.json()
    assert len(r.json()["events"]) >= 1


def test_trading_toggle(client: TestClient):
    r = client.post("/api/trading-enabled", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["trading_enabled"] is False
    p = client.get("/api/portfolio")
    assert p.json()["trading_enabled"] is False
    client.post("/api/trading-enabled", json={"enabled": True})
    p2 = client.get("/api/portfolio")
    assert p2.json()["trading_enabled"] is True


def test_quotes_endpoint(client: TestClient):
    r = client.get("/api/quotes?symbols=AAPL,MSFT")
    assert r.status_code == 200
    quotes = r.json()["quotes"]
    assert len(quotes) == 2
    assert quotes[0]["symbol"] == "AAPL"
    assert quotes[0]["price"] == 180.0


def test_reset_demo(client: TestClient):
    client.post("/api/deposit", json={"amount": 5000.0})
    p1 = client.get("/api/portfolio")
    assert p1.json()["cash"] == 5000.0
    client.post("/api/reset-demo")
    p2 = client.get("/api/portfolio")
    assert p2.json()["cash"] == 0.0


def test_portfolio_positions_enriched(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    client.post(
        "/api/place-order",
        json={"client_order_id": "pe1", "symbol": "AAPL", "side": "BUY", "quantity": 10},
    )
    p = client.get("/api/portfolio").json()
    pos = p["positions"].get("AAPL")
    assert pos is not None
    assert "avg_cost" in pos
    assert "mark_price" in pos
    assert "market_value" in pos
    assert "unrealized_pnl" in pos


def test_risk_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    client.post(
        "/api/place-order",
        json={"client_order_id": "r1", "symbol": "AAPL", "side": "BUY", "quantity": 5},
    )
    r = client.get("/api/risk")
    assert r.status_code == 200
    data = r.json()
    assert "sharpe_ratio" in data
    assert "var_95" in data
    assert "drawdown_curve" in data


def test_agent_registration(client: TestClient):
    r = client.post(
        "/api/agents",
        json={"name": "test-agent", "budget": 10_000.0},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "test-agent"
    assert data["budget"] == 10_000.0

    r2 = client.get("/api/agents")
    assert r2.status_code == 200
    agents = r2.json()["agents"]
    assert len(agents) >= 1


def test_agent_stats_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    r = client.post(
        "/api/agents",
        json={"name": "stat-agent", "budget": 50_000.0},
    )
    agent_id = r.json()["id"]
    client.post(
        "/api/place-order",
        json={
            "client_order_id": "ag1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 5,
            "agent_id": agent_id,
        },
    )
    r2 = client.get(f"/api/agents/{agent_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert data["total_orders"] >= 1


def test_replay_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 5_000.0})
    r = client.get("/api/replay")
    assert r.status_code == 200
    data = r.json()
    assert data["cash"] == 5_000.0
    assert data["total_deposits"] == 5_000.0


def test_event_timeline_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 1_000.0})
    r = client.get("/api/event-timeline")
    assert r.status_code == 200
    data = r.json()
    assert data["max_event_id"] >= 1
    assert len(data["events"]) >= 1


def test_backtest_endpoint(client: TestClient):
    r = client.post(
        "/api/backtest",
        json={
            "name": "api_bt",
            "initial_cash": 100_000,
            "steps": 30,
            "seed": 42,
            "rules": [
                {
                    "type": "buy_below",
                    "symbol": "AAPL",
                    "threshold": 175,
                    "quantity": 5,
                },
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "final_equity" in data
    assert "equity_curve" in data
    assert data["steps"] == 30


def test_metrics_endpoint(client: TestClient):
    client.get("/api/health")
    client.get("/api/health")
    r = client.get("/api/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] >= 2
    assert "latency" in data
    assert "top_endpoints" in data


def test_api_key_management(client: TestClient):
    r = client.post("/api/keys", json={"name": "test-key", "role": "agent"})
    assert r.status_code == 200
    data = r.json()
    assert "raw_key" in data
    assert data["role"] == "agent"
    key_id = data["id"]

    r2 = client.get("/api/keys")
    assert r2.status_code == 200
    assert len(r2.json()["keys"]) >= 1

    r3 = client.delete(f"/api/keys/{key_id}")
    assert r3.status_code == 200
    assert r3.json()["ok"] is True


def test_sweep_fills_endpoint(client: TestClient):
    client.post("/api/deposit", json={"amount": 50_000.0})
    r = client.post("/api/sweep-fills")
    assert r.status_code == 200
    assert "sweeps" in r.json()


def test_observability_headers(client: TestClient):
    r = client.get("/api/health")
    assert "x-request-id" in r.headers
    assert "x-response-time-ms" in r.headers
