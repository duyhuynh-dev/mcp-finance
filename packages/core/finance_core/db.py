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


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Add columns introduced after first release (idempotent)."""
    cols = _table_columns(conn, "orders")
    if "order_kind" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN order_kind TEXT NOT NULL DEFAULT 'MARKET'")
    if "limit_price" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN limit_price REAL")
    fcols = _table_columns(conn, "fills")
    if "fee" not in fcols:
        conn.execute("ALTER TABLE fills ADD COLUMN fee REAL NOT NULL DEFAULT 0")
    conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO account (id, cash, trading_enabled) VALUES (1, 0, 1)"
    )
    migrate_schema(conn)
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
