"""Tests for API key auth and RBAC."""

from __future__ import annotations

import sqlite3

from finance_core.auth import (
    Role,
    create_api_key,
    has_permission,
    list_api_keys,
    revoke_api_key,
    validate_key,
)
from finance_core.db import init_schema


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_create_and_validate() -> None:
    conn = _db()
    api_key, raw = create_api_key(conn, "test-agent", Role.AGENT)
    assert api_key.name == "test-agent"
    assert api_key.role == Role.AGENT
    assert raw.startswith("fsk_")

    validated = validate_key(conn, raw)
    assert validated is not None
    assert validated.id == api_key.id
    assert validated.role == Role.AGENT


def test_invalid_key_returns_none() -> None:
    conn = _db()
    assert validate_key(conn, "fsk_bogus") is None


def test_revoke_key() -> None:
    conn = _db()
    api_key, raw = create_api_key(conn, "temp", Role.VIEWER)
    assert validate_key(conn, raw) is not None

    revoke_api_key(conn, api_key.id)
    assert validate_key(conn, raw) is None


def test_list_keys() -> None:
    conn = _db()
    create_api_key(conn, "k1", Role.ADMIN)
    create_api_key(conn, "k2", Role.AGENT)
    keys = list_api_keys(conn)
    assert len(keys) == 2
    assert keys[0].name == "k1"


def test_permissions() -> None:
    assert has_permission(Role.ADMIN, "trade")
    assert has_permission(Role.ADMIN, "manage_keys")
    assert has_permission(Role.AGENT, "trade")
    assert not has_permission(Role.AGENT, "manage_keys")
    assert has_permission(Role.VIEWER, "read")
    assert not has_permission(Role.VIEWER, "trade")


def test_key_to_dict() -> None:
    conn = _db()
    api_key, _ = create_api_key(conn, "dict-test", Role.AGENT)
    d = api_key.to_dict()
    assert d["name"] == "dict-test"
    assert d["role"] == "agent"
    assert "key_prefix" in d
