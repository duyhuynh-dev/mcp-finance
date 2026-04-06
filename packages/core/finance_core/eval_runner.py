"""Load JSON eval scenarios and assert final ledger state (agent workflow regression)."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from finance_core.ledger import Ledger
from finance_core.market import MockQuoteProvider
from finance_core.policy import PolicyEngine, load_rules_from_dict
from finance_core.types import OrderKind, OrderSide


@dataclass
class EvalResult:
    name: str
    passed: bool
    detail: str


def _apply_step(lg: Ledger, step: dict[str, Any]) -> Any:
    action = step["action"]
    if action == "deposit":
        lg.deposit(float(step["amount"]), actor="eval")
    elif action == "place_order":
        kind = OrderKind(str(step.get("order_kind", "MARKET")).upper())
        lp = step.get("limit_price")
        return lg.place_order(
            str(step["client_order_id"]),
            str(step["symbol"]),
            OrderSide(str(step["side"]).upper()),
            float(step["quantity"]),
            order_kind=kind,
            limit_price=float(lp) if lp is not None else None,
            actor="eval",
        )
    elif action == "cancel_order":
        return lg.cancel_order(int(step["order_id"]), actor="eval")
    elif action == "set_price":
        provider = lg.quotes
        if isinstance(provider, MockQuoteProvider):
            provider.set_price(str(step["symbol"]), float(step["price"]))
    elif action == "tick_limits":
        lg._try_fill_pending_limit_orders()
    elif action == "expect":
        pass
    else:
        raise ValueError(f"Unknown action: {action}")
    return None


def _check_expect(lg: Ledger, step: dict[str, Any]) -> tuple[bool, str]:
    exp_cash = step.get("cash")
    if exp_cash is not None:
        got = lg.get_cash()
        if abs(got - float(exp_cash)) > 0.02:
            return False, f"cash want {exp_cash} got {got}"
    exp_pos = step.get("positions", {})
    for sym, want in exp_pos.items():
        got = lg.position_quantity(sym)
        if abs(got - float(want)) > 1e-6:
            return False, f"position {sym} want {want} got {got}"
    exp_rpnl = step.get("total_realized_pnl")
    if exp_rpnl is not None:
        got = lg._total_realized_pnl()
        if abs(got - float(exp_rpnl)) > 0.02:
            return False, f"realized_pnl want {exp_rpnl} got {got}"
    return True, "ok"


def run_scenario_dict(data: dict[str, Any]) -> EvalResult:
    name = str(data.get("name", "unnamed"))
    quotes = MockQuoteProvider(
        {k.upper(): float(v) for k, v in data["quotes"].items()}
    )
    policy = PolicyEngine(load_rules_from_dict(data["policy"]))
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        lg = Ledger.open(db_path, quotes=quotes, policy=policy)
        for step in data["steps"]:
            if step["action"] == "expect":
                ok, detail = _check_expect(lg, step)
                if not ok:
                    return EvalResult(name=name, passed=False, detail=detail)
            else:
                _apply_step(lg, step)
        return EvalResult(name=name, passed=True, detail="ok")
    finally:
        Path(db_path).unlink(missing_ok=True)


def run_scenario_file(path: str | Path) -> EvalResult:
    p = Path(path)
    data = json.loads(p.read_text())
    return run_scenario_dict(data)


def discover_and_run(scenarios_dir: str | Path) -> list[EvalResult]:
    root = Path(scenarios_dir)
    out: list[EvalResult] = []
    for p in sorted(root.glob("*.json")):
        out.append(run_scenario_file(p))
    return out
