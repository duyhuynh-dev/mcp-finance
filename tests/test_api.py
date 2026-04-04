from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from finance_core.ledger import Ledger

from api.main import app, get_ledger


@pytest.fixture
def client() -> TestClient:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "api.db"
        os.environ["FINANCE_DB_PATH"] = str(db)

        app.dependency_overrides.clear()
        ledger = Ledger.open(str(db))

        def _override() -> Ledger:
            return ledger

        app.dependency_overrides[get_ledger] = _override
        with TestClient(app) as tc:
            yield tc
        app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_deposit_and_portfolio(client: TestClient) -> None:
    r = client.post("/api/deposit", json={"amount": 1000.0})
    assert r.status_code == 200
    p = client.get("/api/portfolio")
    assert p.status_code == 200
    assert p.json()["cash"] == 1000.0
