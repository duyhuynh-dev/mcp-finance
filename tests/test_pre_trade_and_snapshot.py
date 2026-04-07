"""Pre-trade gross cap, risk snapshot, order intents, impact slippage."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.pre_trade_risk import clamp_quantity_for_gross_exposure
from finance_core.types import OrderSide, Position

from api.main import app, get_ledger


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.db"
        import os

        os.environ["FINANCE_DB_PATH"] = str(db)
        app.dependency_overrides.clear()
        quotes = MockQuoteProvider({"AAPL": 100.0})
        policy = PolicyEngine(
            PolicyRules(
                version="t",
                max_shares_per_symbol=10_000.0,
                max_order_notional=500_000.0,
                fee_bps=0.0,
                slippage_bps=0.0,
                max_gross_exposure_multiple=1.5,
            )
        )
        ledger = Ledger.open(str(db), quotes=quotes, policy=policy)

        def _override():
            return ledger

        app.dependency_overrides[get_ledger] = _override
        with TestClient(app) as tc:
            yield tc
        app.dependency_overrides.clear()


def test_clamp_quantity_reduces_for_gross_cap() -> None:
    rules = PolicyRules(
        version="x",
        max_shares_per_symbol=1_000.0,
        max_order_notional=1_000_000.0,
        max_gross_exposure_multiple=1.0,
    )
    positions = {
        "AAPL": Position(
            symbol="AAPL",
            quantity=500.0,
            avg_cost=100.0,
            mark_price=100.0,
            market_value=50_000.0,
            unrealized_pnl=0.0,
        ),
    }
    q, reason = clamp_quantity_for_gross_exposure(
        rules=rules,
        equity=100_000.0,
        positions=positions,
        symbol="MSFT",
        side=OrderSide.BUY,
        quantity=1000.0,
        price=100.0,
    )
    assert reason is None
    assert q < 1000.0
    assert q > 0


def test_risk_snapshot_and_stress(client: TestClient) -> None:
    r = client.get("/api/risk/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert "metrics" in body
    assert "budget" in body
    assert body["budget"]["sufficient_for_budget"] is False
    assert body["policy"]["max_gross_exposure_multiple"] == 1.5

    rb = client.get("/api/risk/budget")
    assert rb.status_code == 200
    assert "return_sample_size" in rb.json()

    client.post("/api/deposit", json={"amount": 50_000.0})
    rs = client.post("/api/risk/stress", json={"shocks": {"AAPL": -0.05}})
    assert rs.status_code == 200


def test_order_intent_create_and_approve(client: TestClient) -> None:
    client.post("/api/deposit", json={"amount": 100_000.0})
    cr = client.post(
        "/api/order-intents",
        json={
            "client_order_id": "hil-1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10.0,
        },
    )
    assert cr.status_code == 200
    intent_id = cr.json()["id"]
    ap = client.post(f"/api/order-intents/{intent_id}/approve")
    assert ap.status_code == 200
    assert ap.json().get("ok") is True


def test_impact_slippage_increases_with_notional() -> None:
    rules = PolicyRules(
        version="z",
        max_shares_per_symbol=1_000_000.0,
        max_order_notional=10_000_000.0,
        slippage_bps=10.0,
        slippage_impact_bps_per_million=50.0,
    )
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "s.db"
        lg = Ledger.open(
            str(db),
            quotes=MockQuoteProvider({"Z": 100.0}),
            policy=PolicyEngine(rules),
        )
        lg.deposit(1_000_000.0, actor="t")
        p1 = lg._apply_slippage(100.0, OrderSide.BUY, order_notional=1_000.0)
        p2 = lg._apply_slippage(100.0, OrderSide.BUY, order_notional=2_000_000.0)
        assert p2 > p1


def test_api_place_order_rejects_on_var_budget_live() -> None:
    import os

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "b.db"
        quotes = MockQuoteProvider({"AAPL": 100.0})
        policy = PolicyEngine(
            PolicyRules(
                version="live-budget",
                max_shares_per_symbol=10_000.0,
                max_order_notional=500_000.0,
                max_portfolio_var_95_pct_of_equity=0.04,
            )
        )
        ledger = Ledger.open(str(db), quotes=quotes, policy=policy)
        ledger.deposit(200_000.0, actor="t")
        ledger.conn.execute("DELETE FROM equity_snapshots")
        e = 100_000.0
        for i in range(16):
            ledger.conn.execute(
                "INSERT INTO equity_snapshots (ts, equity) VALUES (?, ?)",
                (f"2024-01-{i+1:02d}T00:00:00+00:00", e),
            )
            e *= 0.95
        ledger.conn.commit()

        app.dependency_overrides.clear()
        os.environ["BROKER_EXECUTION_MODE"] = "internal"

        def _override():
            return ledger

        app.dependency_overrides[get_ledger] = _override
        with TestClient(app) as tc:
            rb = tc.get("/api/risk/budget")
            assert rb.status_code == 200
            assert rb.json()["sufficient_for_budget"] is True

            r = tc.post(
                "/api/place-order",
                json={
                    "client_order_id": "api-var-1",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": 10.0,
                },
            )
            assert r.status_code == 200
            body = r.json()
            assert body["success"] is False
            assert body["rejection_reason"] == "MAX_VAR_BUDGET"
        app.dependency_overrides.clear()


def test_risk_what_if_projection(client: TestClient) -> None:
    client.post("/api/deposit", json={"amount": 25_000.0})
    r = client.post(
        "/api/risk/what-if",
        json={
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 50.0,
            "order_kind": "MARKET",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["projected_notional"] > 0
    assert "risk_budget" in body
    assert "projected_gross_multiple_after" in body
