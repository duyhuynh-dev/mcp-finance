from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  cash REAL NOT NULL DEFAULT 0,
  trading_enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  budget REAL NOT NULL DEFAULT 0,
  max_order_notional REAL NOT NULL DEFAULT 50000,
  allowed_symbols_json TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_order_id TEXT UNIQUE NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity REAL NOT NULL,
  status TEXT NOT NULL,
  rejection_reason TEXT,
  order_kind TEXT NOT NULL DEFAULT 'MARKET',
  limit_price REAL,
  agent_id INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity REAL NOT NULL,
  price REAL NOT NULL,
  fee REAL NOT NULL DEFAULT 0,
  realized_pnl REAL NOT NULL DEFAULT 0,
  filled_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  result_json TEXT
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  key_hash TEXT UNIQUE NOT NULL,
  key_prefix TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  alert_type TEXT NOT NULL,
  threshold REAL NOT NULL,
  symbol TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  cooldown_seconds INTEGER NOT NULL DEFAULT 300,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id INTEGER NOT NULL REFERENCES alert_rules(id),
  message TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'warning',
  payload_json TEXT,
  fired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_name TEXT NOT NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  strength REAL NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_name TEXT UNIQUE NOT NULL,
  config_json TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  price REAL NOT NULL,
  volume REAL,
  recorded_at TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Add columns introduced after first release (idempotent)."""
    cols = _table_columns(conn, "orders")
    if "order_kind" not in cols:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN order_kind TEXT NOT NULL DEFAULT 'MARKET'"
        )
    if "limit_price" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN limit_price REAL")
    if "agent_id" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN agent_id INTEGER")
    fcols = _table_columns(conn, "fills")
    if "fee" not in fcols:
        conn.execute("ALTER TABLE fills ADD COLUMN fee REAL NOT NULL DEFAULT 0")
    if "realized_pnl" not in fcols:
        conn.execute(
            "ALTER TABLE fills ADD COLUMN realized_pnl REAL NOT NULL DEFAULT 0"
        )
    conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO account (id, cash, trading_enabled) VALUES (1, 0, 1)"
    )
    migrate_schema(conn)
    conn.commit()


@contextmanager
def transaction(
    conn: sqlite3.Connection,
) -> Generator[sqlite3.Connection, None, None]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
