"""API key authentication + role-based access control."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from finance_core.db import transaction
from finance_core.types import utc_now


class Role(StrEnum):
    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "read", "trade", "deposit", "toggle_trading",
        "reset", "manage_agents", "manage_keys",
    },
    Role.AGENT: {"read", "trade"},
    Role.VIEWER: {"read"},
}


@dataclass
class ApiKey:
    id: int
    name: str
    key_prefix: str
    role: Role
    is_active: bool
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_api_key(
    conn: sqlite3.Connection,
    name: str,
    role: Role = Role.AGENT,
) -> tuple[ApiKey, str]:
    """Create a new API key. Returns (ApiKey metadata, raw key string)."""
    raw = f"fsk_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw)
    prefix = raw[:12] + "..."
    ts = utc_now().isoformat()
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO api_keys (name, key_hash, key_prefix, role, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (name, key_hash, prefix, role.value, ts),
        )
        api_key = ApiKey(
            id=int(cur.lastrowid),
            name=name,
            key_prefix=prefix,
            role=role,
            is_active=True,
            created_at=ts,
        )
    return api_key, raw


def validate_key(conn: sqlite3.Connection, raw: str) -> ApiKey | None:
    """Validate a raw API key and return the associated ApiKey, or None."""
    key_hash = _hash_key(raw)
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1",
        (key_hash,),
    ).fetchone()
    if row is None:
        return None
    return ApiKey(
        id=int(row["id"]),
        name=row["name"],
        key_prefix=row["key_prefix"],
        role=Role(row["role"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )


def list_api_keys(conn: sqlite3.Connection) -> list[ApiKey]:
    rows = conn.execute(
        "SELECT * FROM api_keys ORDER BY id ASC"
    ).fetchall()
    return [
        ApiKey(
            id=int(r["id"]),
            name=r["name"],
            key_prefix=r["key_prefix"],
            role=Role(r["role"]),
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


def revoke_api_key(conn: sqlite3.Connection, key_id: int) -> bool:
    with transaction(conn):
        conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,)
        )
    return True


def has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
