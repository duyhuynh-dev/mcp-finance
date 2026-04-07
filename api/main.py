"""REST API with auth, rate limiting, observability, and all trading endpoints."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path, override=True)
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from finance_core.agents import AgentManager
from finance_core.alerts import AlertEngine, AlertType
from finance_core.audit import list_audit
from finance_core.auth import (
    ApiKey,
    Role,
    create_api_key,
    has_permission,
    list_api_keys,
    revoke_api_key,
    validate_key,
)
from finance_core.backtest import BacktestConfig, run_backtest
from finance_core.broadcast import event_bus
from finance_core.events import event_timeline, max_event_id, replay_to_event
from finance_core.execution_events import list_execution_events, replay_summary
from finance_core.execution_quality import build_execution_quality
from finance_core.ledger import Ledger, reset_demo_db
from finance_core.observability import generate_request_id, metrics
from finance_core.order_intents import (
    approve_order_intent,
    create_order_intent,
    list_pending_intents,
    reject_order_intent,
)
from finance_core.policy import PolicyEngine, PolicyRules
from finance_core.pre_trade_risk import (
    clamp_quantity_for_gross_exposure,
    gross_notional,
    projected_gross_after_order,
)
from finance_core.quote_factory import create_quote_provider
from finance_core.ratelimit import rate_limiter
from finance_core.reconciliation import reconcile_ledger_vs_alpaca
from finance_core.request_context import request_id_ctx
from finance_core.risk import (
    build_risk_snapshot,
    compute_risk_metrics,
    stress_book_pnl_impact,
)
from finance_core.risk_budget import build_risk_budget_section, check_var_cvar_budget
from finance_core.signal_alpaca_bridge import forward_pending_strategy_signals
from finance_core.simulator import PriceSimulator
from finance_core.types import OrderKind, OrderSide, OrderStatus, utc_now
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("finance_stack")  # v2

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = str(ROOT / "data" / "finance.db")

REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "").lower() in ("1", "true", "yes")

_ledger: Ledger | None = None
_simulator: PriceSimulator | None = None
_strategy_engine = None

SIMULATE_PRICES = os.environ.get("SIMULATE_PRICES", "1").lower() in ("1", "true", "yes")
EQUITY_SNAPSHOT_INTERVAL_SECONDS = float(
    os.environ.get("EQUITY_SNAPSHOT_INTERVAL_SECONDS", "15")
)

def _float_env(name: str, default: float = 0.0) -> float:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def get_ledger() -> Ledger:
    global _ledger, _simulator, _strategy_engine
    if _ledger is None:
        path = os.environ.get("FINANCE_DB_PATH", DEFAULT_DB)
        quotes = create_quote_provider()
        _ledger = Ledger.open(path, quotes=quotes)
        rules = PolicyRules.default()
        rules = PolicyRules(
            version=rules.version,
            max_shares_per_symbol=rules.max_shares_per_symbol,
            max_order_notional=rules.max_order_notional,
            fee_bps=rules.fee_bps,
            slippage_bps=rules.slippage_bps,
            slippage_impact_bps_per_million=rules.slippage_impact_bps_per_million,
            max_daily_order_count=rules.max_daily_order_count,
            max_portfolio_concentration_pct=rules.max_portfolio_concentration_pct,
            max_gross_exposure_multiple=rules.max_gross_exposure_multiple,
            max_portfolio_var_95_pct_of_equity=_float_env(
                "RISK_MAX_VAR_95_PCT_OF_EQUITY",
                rules.max_portfolio_var_95_pct_of_equity,
            ),
            max_portfolio_cvar_95_pct_of_equity=_float_env(
                "RISK_MAX_CVAR_95_PCT_OF_EQUITY",
                rules.max_portfolio_cvar_95_pct_of_equity,
            ),
        )
        _ledger.set_policy(PolicyEngine(rules))

        from finance_core.market import MockQuoteProvider

        if SIMULATE_PRICES and isinstance(quotes, MockQuoteProvider):
            _simulator = PriceSimulator(quotes, interval=3.0, volatility=0.003)
            _simulator.start()
            log.info("Price simulator started (3s interval, 0.3%% vol)")

        _strategy_engine = _init_strategy_engine(_ledger)
    return _ledger


def _init_strategy_engine(lg: Ledger):
    from finance_core.strategies.factory import build_default_strategy_engine

    engine = build_default_strategy_engine(lg.conn, lg.quotes, interval=60.0)
    log.info("Strategy engine initialized with %d strategies", len(engine.list_strategies()))
    return engine


def get_strategy_engine():
    """Return the shared engine; recreate after app shutdown (e.g. TestClient teardown)."""
    global _strategy_engine
    if _strategy_engine is None:
        lg = get_ledger()
        if _strategy_engine is None:
            _strategy_engine = _init_strategy_engine(lg)
    return _strategy_engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async def _equity_snapshot_loop() -> None:
        if EQUITY_SNAPSHOT_INTERVAL_SECONDS <= 0:
            return
        # Small delay so startup is fully initialized.
        await asyncio.sleep(0.2)
        while True:
            try:
                lg = get_ledger()
                lg.snapshot_equity()
            except Exception:
                # best-effort; don't crash the server
                pass
            await asyncio.sleep(EQUITY_SNAPSHOT_INTERVAL_SECONDS)

    snapshot_task = asyncio.create_task(_equity_snapshot_loop())
    try:
        yield
    finally:
        snapshot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await snapshot_task

    global _simulator, _strategy_engine
    if _simulator:
        _simulator.stop()
        _simulator = None
    if _strategy_engine:
        _strategy_engine.stop()
        _strategy_engine = None


app = FastAPI(title="Finance Stack API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-Id",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-Response-Time-Ms",
    ],
)


# ── observability middleware ─────────────────────────────────

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = generate_request_id()
    request.state.request_id = request_id
    start = time.monotonic()
    token = request_id_ctx.set(request_id)
    try:
        response: Response = await call_next(request)
    finally:
        request_id_ctx.reset(token)

    latency_ms = round((time.monotonic() - start) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Response-Time-Ms"] = str(latency_ms)

    path = request.url.path
    metrics.record(path, response.status_code, latency_ms)

    log.info(
        "%s %s %s %.1fms rid=%s",
        request.method,
        path,
        response.status_code,
        latency_ms,
        request_id,
    )
    return response


# ── auth + rate limit middleware ──────────────────────────────

@app.middleware("http")
async def auth_and_ratelimit_middleware(request: Request, call_next):
    path = request.url.path
    if path in ("/api/health", "/api/metrics", "/docs", "/openapi.json"):
        return await call_next(request)
    if path.startswith("/api/ws"):
        return await call_next(request)

    raw_key = request.headers.get("X-API-Key", "")
    role = "dashboard"
    api_key: ApiKey | None = None

    if raw_key:
        lg = get_ledger()
        api_key = validate_key(lg.conn, raw_key)
        if api_key is None:
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_api_key"},
            )
        role = api_key.role.value
        request.state.api_key = api_key
        request.state.role = api_key.role
    elif REQUIRE_AUTH:
        return JSONResponse(
            status_code=401,
            content={"error": "api_key_required"},
        )
    else:
        request.state.api_key = None
        request.state.role = Role.ADMIN

    limit_key = raw_key or request.client.host if request.client else "anon"
    allowed, headers = rate_limiter.check(limit_key, role)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
            headers=headers,
        )

    response: Response = await call_next(request)
    for k, v in headers.items():
        response.headers[k] = v
    return response


def _require_permission(request: Request, permission: str) -> None:
    role: Role = getattr(request.state, "role", Role.ADMIN)
    if not has_permission(role, permission):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail=f"missing permission: {permission}")


# ── health ───────────────────────────────────────────────────

@app.get("/api/health", response_model=None)
def health() -> Any:
    body: dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "strategy_engine": {"initialized": False, "running": False},
    }
    try:
        lg = get_ledger()
        lg.conn.execute("SELECT 1").fetchone()
        body["database"] = "ok"
    except Exception:
        body["database"] = "error"
        body["status"] = "unhealthy"

    try:
        eng = get_strategy_engine()
        if eng is not None:
            body["strategy_engine"] = {
                "initialized": True,
                "running": eng.is_running,
            }
    except Exception:
        pass

    if os.environ.get("HEALTH_CHECK_ALPACA", "").lower() in ("1", "true", "yes"):
        try:
            from finance_core.broker.alpaca_executor import AlpacaOrderExecutor

            info = AlpacaOrderExecutor().get_account_info()
            body["alpaca"] = "ok" if info.get("connected") else "degraded"
            body["alpaca_detail"] = {k: v for k, v in info.items() if k != "error"}
        except Exception as exc:
            body["alpaca"] = "error"
            body["alpaca_error"] = str(exc)[:200]

    if body["status"] != "ok":
        return JSONResponse(status_code=503, content=body)
    return body


# ── metrics ──────────────────────────────────────────────────

@app.get("/api/metrics")
def get_metrics() -> dict:
    return metrics.snapshot()


# ── portfolio ────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    s = lg.portfolio_state()
    pr = lg.policy_engine.rules
    return {
        "cash": s.cash,
        "equity": lg.estimated_equity(),
        "trading_enabled": s.trading_enabled,
        "total_realized_pnl": s.total_realized_pnl,
        "total_unrealized_pnl": s.total_unrealized_pnl,
        "positions": {
            k: {
                "quantity": v.quantity, "avg_cost": v.avg_cost,
                "mark_price": v.mark_price, "market_value": v.market_value,
                "unrealized_pnl": v.unrealized_pnl,
            }
            for k, v in s.positions.items()
        },
        "rules": {
            "version": pr.version,
            "max_shares_per_symbol": pr.max_shares_per_symbol,
            "max_order_notional": pr.max_order_notional,
            "fee_bps": pr.fee_bps, "slippage_bps": pr.slippage_bps,
            "slippage_impact_bps_per_million": pr.slippage_impact_bps_per_million,
            "max_gross_exposure_multiple": pr.max_gross_exposure_multiple,
            "max_daily_order_count": pr.max_daily_order_count,
            "max_portfolio_concentration_pct": pr.max_portfolio_concentration_pct,
            "max_portfolio_var_95_pct_of_equity": (
                pr.max_portfolio_var_95_pct_of_equity
            ),
            "max_portfolio_cvar_95_pct_of_equity": (
                pr.max_portfolio_cvar_95_pct_of_equity
            ),
        },
    }


# ── orders / fills / equity / audit ──────────────────────────

@app.get("/api/orders")
def orders(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 50) -> dict:
    rows = lg.list_orders(limit=min(limit, 200))
    return {
        "orders": [
            {
                "id": o.id, "client_order_id": o.client_order_id,
                "symbol": o.symbol, "side": o.side.value,
                "quantity": o.quantity, "status": o.status.value,
                "rejection_reason": o.rejection_reason.value if o.rejection_reason else None,
                "order_kind": o.order_kind.value, "limit_price": o.limit_price,
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
                "id": f.id, "order_id": f.order_id, "symbol": f.symbol,
                "side": f.side.value, "quantity": f.quantity,
                "price": f.price, "fee": f.fee,
                "realized_pnl": f.realized_pnl,
                "filled_at": f.filled_at.isoformat(),
            }
            for f in rows
        ]
    }


@app.get("/api/equity-series")
def equity_series(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 200) -> dict:
    return {"points": lg.equity_series(limit=min(limit, 500))}


@app.get("/api/audit")
def audit(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 80, offset: int = 0) -> dict:
    return {"events": list_audit(lg.conn, limit=min(limit, 200), offset=offset)}


@app.get("/api/execution-events")
def execution_events(
    lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 100, offset: int = 0,
) -> dict:
    return {
        "events": list_execution_events(
            lg.conn, limit=min(limit, 500), offset=max(offset, 0),
        ),
    }


@app.get("/api/execution-events/replay")
def execution_replay(
    lg: Annotated[Ledger, Depends(get_ledger)],
    to_event_id: int | None = None,
) -> dict:
    return replay_summary(lg.conn, to_event_id=to_event_id)


@app.get("/api/execution/quality")
def execution_quality(
    lg: Annotated[Ledger, Depends(get_ledger)], limit_orders: int = 500,
) -> dict:
    return build_execution_quality(lg.conn, limit_orders=limit_orders)


@app.get("/api/quotes")
def quotes(lg: Annotated[Ledger, Depends(get_ledger)], symbols: str = "") -> dict:
    provider = lg.quotes
    syms = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols.strip() else provider.list_symbols()
    )
    out: list[dict] = []
    for sym in syms:
        try:
            q = provider.get_quote(sym)
            out.append({"symbol": q.symbol, "price": q.price, "as_of": q.as_of.isoformat()})
        except ValueError:
            out.append({"symbol": sym, "price": None, "error": "unknown"})
    return {"quotes": out}


# ── mutations ────────────────────────────────────────────────

class DepositBody(BaseModel):
    amount: float = Field(gt=0)


@app.post("/api/deposit")
def deposit(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: DepositBody,
) -> dict:
    _require_permission(request, "deposit")
    cash = lg.deposit(body.amount, actor="dashboard")
    return {"cash": cash}


class TradingBody(BaseModel):
    enabled: bool


@app.post("/api/trading-enabled")
def trading_enabled(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: TradingBody,
) -> dict:
    _require_permission(request, "toggle_trading")
    lg.set_trading_enabled(body.enabled, actor="dashboard")
    return {"trading_enabled": body.enabled}


class PlaceOrderBody(BaseModel):
    client_order_id: str
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    order_kind: str = "MARKET"
    limit_price: float | None = None
    agent_id: int | None = None


@app.post("/api/place-order")
def place_order_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: PlaceOrderBody,
) -> dict:
    _require_permission(request, "trade")
    s = OrderSide(body.side.strip().upper())
    k = OrderKind(body.order_kind.strip().upper())
    broker_exec = os.environ.get("BROKER_EXECUTION_MODE", "").lower() in (
        "alpaca",
        "alpaca_paper",
    )
    if broker_exec:
        from finance_core.broker.alpaca_executor import AlpacaOrderExecutor

        try:
            ex = AlpacaOrderExecutor()
            er = ex.submit_order(
                body.symbol,
                s.value,
                body.quantity,
                order_type="limit" if k == OrderKind.LIMIT else "market",
                limit_price=body.limit_price,
            )
        except Exception as exc:
            return {
                "success": False,
                "status": "REJECTED",
                "message": f"broker_submit_failed: {exc}",
            }

        status = OrderStatus.PENDING
        if er.fill_quantity >= body.quantity - 1e-9:
            status = OrderStatus.FILLED
        elif er.fill_quantity > 1e-9:
            status = OrderStatus.PARTIAL

        mirrored = lg.mirror_broker_execution(
            client_order_id=body.client_order_id.strip(),
            symbol=body.symbol,
            side=s,
            quantity=body.quantity,
            status=status,
            fill_price=er.fill_price if er.fill_quantity > 0 else None,
            filled_quantity=er.fill_quantity,
            broker_order_id=er.broker_order_id,
            actor="dashboard_broker",
            order_kind=k,
            limit_price=body.limit_price,
            agent_id=body.agent_id,
            fees=er.fees,
        ).to_audit_dict()
        mirrored["broker_mode"] = "alpaca_paper"
        mirrored["broker_order_id"] = er.broker_order_id
        return mirrored

    r = lg.place_order(
        body.client_order_id.strip(), body.symbol, s, body.quantity,
        order_kind=k, limit_price=body.limit_price,
        actor="dashboard", agent_id=body.agent_id,
    )
    return r.to_audit_dict()


@app.post("/api/reset-demo")
def reset_demo(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)],
) -> dict:
    _require_permission(request, "reset")
    global _ledger
    reset_demo_db(lg.conn)
    _ledger = None
    return {"ok": True}


@app.post("/api/cancel-order/{order_id}")
def cancel_order_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], order_id: int,
) -> dict:
    _require_permission(request, "trade")
    return lg.cancel_order(order_id, actor="dashboard")


@app.post("/api/sweep-fills")
def sweep_fills_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)],
) -> dict:
    """Try to fill remaining quantity on all PARTIAL orders."""
    _require_permission(request, "trade")
    from finance_core.orderbook import LiquidityConfig

    results = lg.sweep_partial_orders(LiquidityConfig())
    return {"sweeps": results}


# ── risk analytics ───────────────────────────────────────────

@app.get("/api/risk")
def risk_metrics(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    return compute_risk_metrics(lg.conn).to_dict()


@app.get("/api/risk/snapshot")
def risk_snapshot(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    return build_risk_snapshot(lg.conn, lg)


@app.get("/api/risk/budget")
def risk_budget(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    return build_risk_budget_section(lg.conn, lg.policy_engine.rules)


class StressBody(BaseModel):
    shocks: dict[str, float] = Field(default_factory=dict)


class RiskWhatIfBody(BaseModel):
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    order_kind: str = "MARKET"
    limit_price: float | None = None


def _evaluate_risk_what_if(lg: Ledger, body: RiskWhatIfBody) -> dict[str, Any]:
    sym = body.symbol.strip().upper()
    side = OrderSide(body.side.strip().upper())
    order_kind = OrderKind(body.order_kind.strip().upper())
    if order_kind == OrderKind.LIMIT and (body.limit_price is None or body.limit_price <= 0):
        return {"allowed": False, "reason": "INVALID_LIMIT_PRICE"}
    if not lg.get_trading_enabled():
        return {"allowed": False, "reason": "TRADING_DISABLED"}
    try:
        quote = lg.quotes.get_quote(sym)
        mark = quote.price
    except ValueError:
        return {"allowed": False, "reason": "UNKNOWN_SYMBOL"}

    policy_price = body.limit_price if order_kind == OrderKind.LIMIT else mark
    assert policy_price is not None
    state = lg.portfolio_state()
    equity = lg.estimated_equity()
    pos_now = lg.position_quantity(sym)
    pos_after = pos_now + body.quantity if side == OrderSide.BUY else pos_now - body.quantity
    pr = lg.policy_engine.check(
        symbol=sym,
        side=side,
        quantity=body.quantity,
        price=float(policy_price),
        state=state,
        position_after=pos_after,
        daily_order_count=lg._daily_order_count(),
        equity=equity,
    )
    if not pr.allowed and pr.reason:
        return {"allowed": False, "reason": pr.reason.value}

    q_adj, rpre = clamp_quantity_for_gross_exposure(
        rules=lg.policy_engine.rules,
        equity=equity,
        positions=state.positions,
        symbol=sym,
        side=side,
        quantity=body.quantity,
        price=float(policy_price),
    )
    if rpre is not None:
        return {"allowed": False, "reason": rpre.value}

    rb = check_var_cvar_budget(
        lg.conn,
        lg.policy_engine.rules,
        state.positions,
        sym,
        side,
        q_adj,
        float(policy_price),
    )
    if rb is not None:
        return {"allowed": False, "reason": rb.value}

    gross_now = gross_notional(state.positions)
    gross_after = projected_gross_after_order(
        positions=state.positions,
        symbol=sym,
        side=side,
        quantity=q_adj,
        price=float(policy_price),
    )
    gross_multiple_after = (gross_after / equity) if equity > 1e-9 else None
    notional = q_adj * float(policy_price)
    est_fill = lg._apply_slippage(mark, side, q_adj * mark)
    est_fee = lg._fee_amount(notional)
    return {
        "allowed": True,
        "reason": None,
        "symbol": sym,
        "side": side.value,
        "order_kind": order_kind.value,
        "requested_quantity": body.quantity,
        "adjusted_quantity": q_adj,
        "would_resize": q_adj + 1e-9 < body.quantity,
        "estimated_mark_price": round(mark, 6),
        "estimated_fill_price": round(est_fill, 6),
        "projected_notional": round(notional, 2),
        "estimated_fee": round(est_fee, 6),
        "projected_gross_notional_before": round(gross_now, 2),
        "projected_gross_notional_after": round(gross_after, 2),
        "projected_gross_multiple_after": (
            round(gross_multiple_after, 4) if gross_multiple_after is not None else None
        ),
        "risk_budget": build_risk_budget_section(lg.conn, lg.policy_engine.rules),
    }


@app.post("/api/risk/what-if")
def risk_what_if(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: RiskWhatIfBody,
) -> dict:
    _require_permission(request, "trade")
    return _evaluate_risk_what_if(lg, body)


class SimulationScenarioCreateBody(BaseModel):
    name: str
    description: str = ""
    legs: list[RiskWhatIfBody]
    note: str = ""


@app.get("/api/sim/scenarios")
def list_sim_scenarios(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 100,
) -> dict:
    _require_permission(request, "trade")
    rows = lg.conn.execute(
        "SELECT id, name, description, scenario_json, created_at, updated_at, current_revision "
        "FROM simulation_scenarios ORDER BY id DESC LIMIT ?",
        (min(limit, 200),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        payload = json.loads(str(r["scenario_json"]))
        vrow = lg.conn.execute(
            "SELECT COUNT(*) AS c FROM simulation_scenario_versions WHERE scenario_id = ?",
            (int(r["id"]),),
        ).fetchone()
        out.append({
            "id": int(r["id"]),
            "name": r["name"],
            "description": r["description"] or "",
            "legs": payload.get("legs", []),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"] or r["created_at"],
            "current_revision": int(r["current_revision"] or 1),
            "version_count": int(vrow["c"]) if vrow else 1,
        })
    return {"scenarios": out}


@app.post("/api/sim/scenarios")
def create_sim_scenario(
    request: Request,
    lg: Annotated[Ledger, Depends(get_ledger)],
    body: SimulationScenarioCreateBody,
) -> dict:
    _require_permission(request, "trade")
    if not body.legs:
        raise HTTPException(status_code=400, detail="at least one leg required")
    ts = utc_now().isoformat()
    payload = json.dumps({
        "legs": [leg.model_dump() for leg in body.legs],
    })
    name = body.name.strip()
    row = lg.conn.execute(
        "SELECT id, current_revision FROM simulation_scenarios WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        cur = lg.conn.execute(
            "INSERT INTO simulation_scenarios "
            "(name, description, scenario_json, created_at, updated_at, current_revision) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (name, body.description.strip(), payload, ts, ts),
        )
        scenario_id = int(cur.lastrowid)
        revision = 1
    else:
        scenario_id = int(row["id"])
        revision = int(row["current_revision"]) + 1
        lg.conn.execute(
            "UPDATE simulation_scenarios "
            "SET description = ?, scenario_json = ?, updated_at = ?, current_revision = ? "
            "WHERE id = ?",
            (body.description.strip(), payload, ts, revision, scenario_id),
        )
    lg.conn.execute(
        "INSERT OR REPLACE INTO simulation_scenario_versions "
        "(scenario_id, revision, scenario_json, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (scenario_id, revision, payload, body.note.strip(), ts),
    )
    lg.conn.commit()
    return {
        "id": scenario_id,
        "name": name,
        "created_at": ts,
        "revision": revision,
    }


@app.get("/api/sim/scenarios/{scenario_id}/versions")
def list_sim_scenario_versions(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], scenario_id: int,
) -> dict:
    _require_permission(request, "trade")
    rows = lg.conn.execute(
        "SELECT id, revision, scenario_json, note, created_at "
        "FROM simulation_scenario_versions WHERE scenario_id = ? ORDER BY revision DESC",
        (scenario_id,),
    ).fetchall()
    versions: list[dict[str, Any]] = []
    for r in rows:
        payload = json.loads(str(r["scenario_json"]))
        versions.append({
            "id": int(r["id"]),
            "revision": int(r["revision"]),
            "legs": payload.get("legs", []),
            "note": r["note"] or "",
            "created_at": r["created_at"],
        })
    return {"versions": versions}


@app.delete("/api/sim/scenarios/{scenario_id}")
def delete_sim_scenario(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], scenario_id: int,
) -> dict:
    _require_permission(request, "trade")
    lg.conn.execute("DELETE FROM simulation_scenarios WHERE id = ?", (scenario_id,))
    lg.conn.commit()
    return {"ok": True}


class SimulationRunBody(BaseModel):
    scenario_id: int | None = None
    legs: list[RiskWhatIfBody] = Field(default_factory=list)


def _load_scenario_legs(conn: Any, scenario_id: int) -> tuple[str, list[RiskWhatIfBody]]:
    row = conn.execute(
        "SELECT name, scenario_json, current_revision FROM simulation_scenarios WHERE id = ?",
        (scenario_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    scenario_name = str(row["name"])
    vrow = conn.execute(
        "SELECT scenario_json FROM simulation_scenario_versions "
        "WHERE scenario_id = ? AND revision = ?",
        (scenario_id, int(row["current_revision"] or 1)),
    ).fetchone()
    payload = (
        json.loads(str(vrow["scenario_json"]))
        if vrow else json.loads(str(row["scenario_json"]))
    )
    legs = [RiskWhatIfBody(**x) for x in payload.get("legs", [])]
    return scenario_name, legs


def _summarize_sim_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = [r for r in results if r.get("allowed")]
    rejected = [r for r in results if not r.get("allowed")]
    reason_counts: dict[str, int] = {}
    for r in rejected:
        rs = str(r.get("reason") or "UNKNOWN")
        reason_counts[rs] = reason_counts.get(rs, 0) + 1
    top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
    return {
        "legs": len(results),
        "allowed": len(allowed),
        "rejected": len(rejected),
        "acceptance_rate": round(len(allowed) / len(results), 4) if results else 0.0,
        "projected_notional_allowed": round(
            sum(float(r.get("projected_notional") or 0.0) for r in allowed), 2,
        ),
        "top_rejection_reasons": [
            {"reason": k, "count": v} for k, v in top_reasons[:5]
        ],
    }


@app.post("/api/sim/run")
def run_simulation(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: SimulationRunBody,
) -> dict:
    _require_permission(request, "trade")
    legs: list[RiskWhatIfBody] = []
    scenario_name: str | None = None
    if body.scenario_id is not None:
        scenario_name, legs = _load_scenario_legs(lg.conn, body.scenario_id)
    elif body.legs:
        legs = body.legs
    else:
        raise HTTPException(status_code=400, detail="scenario_id or legs required")

    results = [_evaluate_risk_what_if(lg, leg) for leg in legs]
    return {
        "scenario_name": scenario_name,
        "summary": _summarize_sim_results(results),
        "results": results,
    }


class SimulationCompareBody(BaseModel):
    baseline_scenario_id: int
    candidate_scenario_id: int


@app.post("/api/sim/compare")
def compare_simulations(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: SimulationCompareBody,
) -> dict:
    _require_permission(request, "trade")
    baseline_name, baseline_legs = _load_scenario_legs(lg.conn, body.baseline_scenario_id)
    candidate_name, candidate_legs = _load_scenario_legs(lg.conn, body.candidate_scenario_id)
    base_results = [_evaluate_risk_what_if(lg, leg) for leg in baseline_legs]
    cand_results = [_evaluate_risk_what_if(lg, leg) for leg in candidate_legs]
    base_summary = _summarize_sim_results(base_results)
    cand_summary = _summarize_sim_results(cand_results)
    return {
        "baseline": {
            "id": body.baseline_scenario_id,
            "name": baseline_name,
            "summary": base_summary,
        },
        "candidate": {
            "id": body.candidate_scenario_id,
            "name": candidate_name,
            "summary": cand_summary,
        },
        "delta": {
            "acceptance_rate": round(
                float(cand_summary["acceptance_rate"]) - float(base_summary["acceptance_rate"]),
                4,
            ),
            "projected_notional_allowed": round(
                float(cand_summary["projected_notional_allowed"])
                - float(base_summary["projected_notional_allowed"]),
                2,
            ),
            "rejected": int(cand_summary["rejected"]) - int(base_summary["rejected"]),
        },
    }


class SimulationPromoteBody(BaseModel):
    baseline_scenario_id: int
    candidate_scenario_id: int
    note: str = "promoted from candidate"


@app.post("/api/sim/promote")
def promote_simulation_candidate(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: SimulationPromoteBody,
) -> dict:
    _require_permission(request, "trade")
    _, candidate_legs = _load_scenario_legs(lg.conn, body.candidate_scenario_id)
    b_row = lg.conn.execute(
        "SELECT id, name, description, current_revision FROM simulation_scenarios WHERE id = ?",
        (body.baseline_scenario_id,),
    ).fetchone()
    if b_row is None:
        raise HTTPException(status_code=404, detail="baseline scenario not found")
    ts = utc_now().isoformat()
    revision = int(b_row["current_revision"] or 1) + 1
    payload = json.dumps({"legs": [leg.model_dump() for leg in candidate_legs]})
    lg.conn.execute(
        "UPDATE simulation_scenarios "
        "SET scenario_json = ?, updated_at = ?, current_revision = ? WHERE id = ?",
        (payload, ts, revision, body.baseline_scenario_id),
    )
    lg.conn.execute(
        "INSERT INTO simulation_scenario_versions "
        "(scenario_id, revision, scenario_json, note, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (body.baseline_scenario_id, revision, payload, body.note, ts),
    )
    lg.conn.commit()
    return {
        "ok": True,
        "baseline_scenario_id": body.baseline_scenario_id,
        "baseline_name": b_row["name"],
        "new_revision": revision,
    }


@app.post("/api/risk/stress")
def risk_stress(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: StressBody,
) -> dict:
    _require_permission(request, "trade")
    return stress_book_pnl_impact(lg, body.shocks)


@app.get("/api/broker/reconciliation")
def broker_reconciliation(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)],
) -> dict:
    _require_permission(request, "trade")
    return reconcile_ledger_vs_alpaca(lg)


class OrderIntentCreateBody(BaseModel):
    client_order_id: str
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    order_kind: str = "MARKET"
    limit_price: float | None = None
    agent_id: int | None = None


@app.post("/api/order-intents")
def create_order_intent_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: OrderIntentCreateBody,
) -> dict:
    _require_permission(request, "trade")
    return create_order_intent(
        lg.conn,
        client_order_id=body.client_order_id,
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
        order_kind=body.order_kind,
        limit_price=body.limit_price,
        agent_id=body.agent_id,
        actor="dashboard",
    )


@app.get("/api/order-intents/pending")
def list_order_intents_pending(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 50,
) -> dict:
    _require_permission(request, "trade")
    return {"intents": list_pending_intents(lg.conn, limit=min(limit, 200))}


@app.post("/api/order-intents/{intent_id}/approve")
def approve_order_intent_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], intent_id: int,
) -> dict:
    _require_permission(request, "manage_agents")
    return approve_order_intent(lg, intent_id, actor="dashboard")


@app.post("/api/order-intents/{intent_id}/reject")
def reject_order_intent_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], intent_id: int,
) -> dict:
    _require_permission(request, "manage_agents")
    return reject_order_intent(lg.conn, intent_id)


@app.post("/api/strategies/forward-signals-alpaca")
def forward_signals_alpaca_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)],
    max_rows: int = 25,
    max_qty: float = 5.0,
) -> dict:
    _require_permission(request, "manage_agents")
    if os.environ.get("SIGNALS_TO_ALPACA", "").lower() not in ("1", "true", "yes"):
        return {"error": "disabled", "hint": "set SIGNALS_TO_ALPACA=1"}
    from finance_core.broker.alpaca_executor import AlpacaOrderExecutor

    try:
        exe = AlpacaOrderExecutor()
    except Exception as exc:
        return {"error": str(exc)}
    return forward_pending_strategy_signals(
        lg.conn, exe, max_rows=min(max_rows, 100), max_qty=max_qty,
    )


# ── agents ───────────────────────────────────────────────────

class RegisterAgentBody(BaseModel):
    name: str
    budget: float = Field(gt=0)
    max_order_notional: float = 50_000.0
    allowed_symbols: list[str] | None = None
    allowed_mcp_tools: list[str] | None = None


@app.post("/api/agents")
def register_agent(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: RegisterAgentBody,
) -> dict:
    _require_permission(request, "manage_agents")
    mgr = AgentManager(lg.conn)
    return mgr.register(
        body.name,
        body.budget,
        body.max_order_notional,
        body.allowed_symbols,
        allowed_mcp_tools=body.allowed_mcp_tools,
    ).to_dict()


@app.get("/api/agents")
def list_agents_endpoint(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    return {"agents": [a.to_dict() for a in AgentManager(lg.conn).list_all()]}


@app.get("/api/agents/{agent_id}")
def get_agent(lg: Annotated[Ledger, Depends(get_ledger)], agent_id: int) -> dict:
    s = AgentManager(lg.conn).stats(agent_id)
    return s.to_dict() if s else {"error": "agent not found"}


# ── API keys ─────────────────────────────────────────────────

class CreateKeyBody(BaseModel):
    name: str
    role: str = "agent"


@app.post("/api/keys")
def create_key_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: CreateKeyBody,
) -> dict:
    _require_permission(request, "manage_keys")
    role = Role(body.role.strip().lower())
    api_key, raw = create_api_key(lg.conn, body.name, role)
    return {**api_key.to_dict(), "raw_key": raw}


@app.get("/api/keys")
def list_keys_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)],
) -> dict:
    _require_permission(request, "manage_keys")
    return {"keys": [k.to_dict() for k in list_api_keys(lg.conn)]}


@app.delete("/api/keys/{key_id}")
def revoke_key_endpoint(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], key_id: int,
) -> dict:
    _require_permission(request, "manage_keys")
    revoke_api_key(lg.conn, key_id)
    return {"ok": True}


# ── event sourcing / replay ──────────────────────────────────

@app.get("/api/replay")
def replay(lg: Annotated[Ledger, Depends(get_ledger)], event_id: int = 0) -> dict:
    eid = event_id if event_id > 0 else max_event_id(lg.conn)
    return replay_to_event(lg.conn, eid).to_dict()


@app.get("/api/event-timeline")
def get_event_timeline(lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 200) -> dict:
    return {
        "events": event_timeline(lg.conn, limit=min(limit, 500)),
        "max_event_id": max_event_id(lg.conn),
    }


# ── backtesting ──────────────────────────────────────────────

class BacktestBody(BaseModel):
    name: str = "backtest"
    initial_cash: float = 100_000.0
    rules: list[dict[str, Any]]
    steps: int = 100
    seed: int = 42
    drift: float = 0.0005
    volatility: float = 0.02
    start_prices: dict[str, float] | None = None
    policy: dict[str, Any] | None = None


@app.post("/api/backtest")
def run_backtest_endpoint(
    lg: Annotated[Ledger, Depends(get_ledger)], body: BacktestBody,
) -> dict:
    import json as _json

    config = BacktestConfig.from_dict(body.model_dump())
    result = run_backtest(config)
    from finance_core.types import utc_now

    ts = utc_now().isoformat()
    sql = (
        "INSERT INTO backtest_runs"
        " (name, config_json, result_json, created_at)"
        " VALUES (?, ?, ?, ?)"
    )
    lg.conn.execute(sql, (
        config.name,
        _json.dumps(body.model_dump()),
        _json.dumps(result.to_dict()),
        ts,
    ))
    lg.conn.commit()
    return result.to_dict()


@app.get("/api/backtest-history")
def backtest_history(
    lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 20,
) -> dict:
    import json as _json

    rows = lg.conn.execute(
        "SELECT * FROM backtest_runs ORDER BY id DESC LIMIT ?",
        (min(limit, 50),),
    ).fetchall()
    return {
        "runs": [
            {
                "id": int(r["id"]),
                "name": r["name"],
                "result": _json.loads(r["result_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    }


# ── alerts ───────────────────────────────────────────────────

class CreateAlertBody(BaseModel):
    name: str
    alert_type: str
    threshold: float
    symbol: str | None = None
    cooldown_seconds: int = 300


@app.post("/api/alerts")
def create_alert(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], body: CreateAlertBody,
) -> dict:
    _require_permission(request, "manage_agents")
    engine = AlertEngine(lg.conn)
    rule = engine.create_rule(
        body.name,
        AlertType(body.alert_type),
        body.threshold,
        body.symbol,
        body.cooldown_seconds,
    )
    return rule.to_dict()


@app.get("/api/alerts")
def list_alerts(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    engine = AlertEngine(lg.conn)
    return {"rules": [r.to_dict() for r in engine.list_rules()]}


@app.delete("/api/alerts/{rule_id}")
def delete_alert(
    request: Request, lg: Annotated[Ledger, Depends(get_ledger)], rule_id: int,
) -> dict:
    _require_permission(request, "manage_agents")
    AlertEngine(lg.conn).delete_rule(rule_id)
    return {"ok": True}


@app.get("/api/alert-notifications")
def alert_notifications(
    lg: Annotated[Ledger, Depends(get_ledger)], limit: int = 50,
) -> dict:
    engine = AlertEngine(lg.conn)
    return {"notifications": [n.to_dict() for n in engine.list_notifications(limit)]}


@app.post("/api/alerts/evaluate")
def evaluate_alerts(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    """Manually trigger alert evaluation against current portfolio state."""
    from finance_core.risk import compute_risk_metrics

    engine = AlertEngine(lg.conn)
    state = lg.portfolio_state()
    risk = compute_risk_metrics(lg.conn)

    positions_value: dict[str, float] = {}
    for sym, pos in state.positions.items():
        positions_value[sym] = pos.market_value

    fired = engine.evaluate(
        equity=lg.estimated_equity(),
        cash=state.cash,
        positions=positions_value,
        realized_pnl=state.total_realized_pnl,
        max_drawdown_pct=risk.max_drawdown_pct,
        risk_budget_max_utilization=build_risk_budget_section(
            lg.conn, lg.policy_engine.rules,
        ).get("max_utilization"),
    )
    return {"fired": [n.to_dict() for n in fired]}


# ── quote provider info ──────────────────────────────────────

@app.get("/api/quote-backend")
def quote_backend_info(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    from finance_core.market import CachedQuoteProvider

    provider = lg.quotes
    backend = "mock"
    cache_stats: dict = {}
    if isinstance(provider, CachedQuoteProvider):
        backend = "yahoo (cached)"
        cache_stats = provider.cache_stats()
    return {
        "backend": backend,
        "symbols": provider.list_symbols(),
        "simulator_active": _simulator.is_running if _simulator else False,
        **cache_stats,
    }


class SimulatorBody(BaseModel):
    enabled: bool


@app.post("/api/simulator")
def toggle_simulator(body: SimulatorBody) -> dict:
    global _simulator
    from finance_core.market import MockQuoteProvider

    lg = get_ledger()
    if body.enabled:
        if _simulator and _simulator.is_running:
            return {"status": "already_running"}
        if not isinstance(lg.quotes, MockQuoteProvider):
            return {"status": "not_mock_backend"}
        _simulator = PriceSimulator(lg.quotes)
        _simulator.start()
        return {"status": "started"}
    else:
        if _simulator:
            _simulator.stop()
        return {"status": "stopped"}


# ── strategies ────────────────────────────────────────────────

@app.get("/api/strategies")
def list_strategies() -> dict:
    engine = get_strategy_engine()
    if not engine:
        return {"strategies": []}
    return {"strategies": engine.list_strategies()}


@app.post("/api/strategies/{name}/toggle")
def toggle_strategy(request: Request, name: str) -> dict:
    _require_permission(request, "manage_agents")
    engine = get_strategy_engine()
    if not engine:
        return {"error": "strategy engine not initialized"}
    strat = engine.get_strategy(name)
    if not strat:
        return {"error": f"unknown strategy: {name}"}
    is_active = name in engine._active
    if is_active:
        engine.deactivate(name)
        return {"name": name, "active": False}
    else:
        engine.activate(name)
        return {"name": name, "active": True}


class ConfigureStrategyBody(BaseModel):
    params: dict[str, Any]


@app.post("/api/strategies/{name}/configure")
def configure_strategy(
    request: Request, name: str, body: ConfigureStrategyBody,
) -> dict:
    _require_permission(request, "manage_agents")
    engine = get_strategy_engine()
    if not engine:
        return {"error": "strategy engine not initialized"}
    strat = engine.get_strategy(name)
    if not strat:
        return {"error": f"unknown strategy: {name}"}
    strat.configure(body.params)
    return {"name": name, "config": strat.get_config()}


@app.get("/api/strategies/{name}/diagnostics")
def strategy_diagnostics(name: str) -> dict:
    """Rich diagnostics for strategies that implement export_diagnostics (e.g. ml_alpha)."""
    engine = get_strategy_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="strategy engine not initialized")
    strat = engine.get_strategy(name)
    if not strat:
        raise HTTPException(status_code=404, detail=f"unknown strategy: {name}")
    export = getattr(strat, "export_diagnostics", None)
    if not callable(export):
        raise HTTPException(
            status_code=404,
            detail="diagnostics not available for this strategy",
        )
    return export()


@app.get("/api/strategies/{name}/signals")
def strategy_signals(name: str, limit: int = 50) -> dict:
    engine = get_strategy_engine()
    if not engine:
        return {"signals": []}
    return {"signals": engine.recent_signals(name, limit=min(limit, 200))}


@app.get("/api/strategies/signals")
def all_signals(limit: int = 50) -> dict:
    engine = get_strategy_engine()
    if not engine:
        return {"signals": []}
    return {"signals": engine.recent_signals(limit=min(limit, 200))}


@app.post("/api/strategies/run-once")
def run_strategies_once(request: Request) -> dict:
    """Manually trigger one cycle of all active strategies."""
    _require_permission(request, "trade")
    engine = get_strategy_engine()
    if not engine:
        return {"signals": []}
    signals = engine.run_once()
    return {"signals": [s.to_dict() for s in signals]}


@app.post("/api/strategies/start-engine")
def start_strategy_engine(request: Request) -> dict:
    _require_permission(request, "manage_agents")
    engine = get_strategy_engine()
    if not engine:
        return {"error": "strategy engine not initialized"}
    engine.start()
    return {"status": "running"}


@app.post("/api/strategies/stop-engine")
def stop_strategy_engine(request: Request) -> dict:
    _require_permission(request, "manage_agents")
    engine = get_strategy_engine()
    if not engine:
        return {"error": "strategy engine not initialized"}
    engine.stop()
    return {"status": "stopped"}


# ── broker status ─────────────────────────────────────────────

@app.get("/api/broker-status")
def broker_status(lg: Annotated[Ledger, Depends(get_ledger)]) -> dict:
    from finance_core.broker.alpaca_provider import AlpacaQuoteProvider
    from finance_core.market import CachedQuoteProvider

    provider = lg.quotes
    backend = "mock"
    broker_info: dict[str, Any] = {"connected": False}

    if isinstance(provider, CachedQuoteProvider):
        inner = provider._inner
        if isinstance(inner, AlpacaQuoteProvider):
            backend = "alpaca"
            from finance_core.broker.alpaca_executor import AlpacaOrderExecutor

            try:
                executor = AlpacaOrderExecutor()
                broker_info = executor.get_account_info()
            except Exception as e:
                broker_info = {"connected": False, "error": str(e)}
        else:
            backend = "yahoo"

    return {
        "backend": backend,
        "broker": broker_info,
        "simulator_active": _simulator.is_running if _simulator else False,
        "strategy_engine_running": (
            _strategy_engine._thread.is_alive()
            if _strategy_engine and _strategy_engine._thread
            else False
        ),
    }


# ── VWAP/TWAP execution ──────────────────────────────────────

class ExecutionPlanBody(BaseModel):
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    algorithm: str = "TWAP"
    num_slices: int = 10
    interval_seconds: int = 60
    benchmark_price: float = 0.0


@app.post("/api/execution-plan")
def create_execution_plan(
    request: Request,
    lg: Annotated[Ledger, Depends(get_ledger)],
    body: ExecutionPlanBody,
) -> dict:
    _require_permission(request, "trade")
    from finance_core.strategies.vwap_twap import TWAPExecutor, VWAPExecutor

    benchmark = body.benchmark_price
    if benchmark <= 0:
        try:
            benchmark = lg.quotes.get_quote(body.symbol).price
        except ValueError:
            benchmark = 0

    if body.algorithm.upper() == "VWAP":
        executor = VWAPExecutor(body.num_slices, body.interval_seconds)
        plan = executor.create_plan(
            body.symbol, body.side, body.quantity,
            benchmark_price=benchmark,
        )
    else:
        executor = TWAPExecutor(body.num_slices, body.interval_seconds)
        plan = executor.create_plan(
            body.symbol, body.side, body.quantity,
            benchmark_price=benchmark,
        )
    return plan.to_dict()


# ── WebSocket ────────────────────────────────────────────────

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    q = event_bus.subscribe()
    snapshot_counter = 0
    try:
        while True:
            while q:
                event = q.popleft()
                await websocket.send_json(event)
                if event.get("type") == "price_tick":
                    snapshot_counter += 1
                    if snapshot_counter % 3 == 0:
                        try:
                            lg = get_ledger()
                            lg._maybe_snapshot_equity()
                        except Exception:
                            pass
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        event_bus.unsubscribe(q)


def create_app() -> FastAPI:
    return app
