"""Tests for token bucket rate limiter."""

from __future__ import annotations

from finance_core.ratelimit import RateLimiter


def test_basic_allow() -> None:
    rl = RateLimiter()
    allowed, headers = rl.check("user-1", "dashboard")
    assert allowed is True
    assert "X-RateLimit-Limit" in headers
    assert "X-RateLimit-Remaining" in headers


def test_exhaust_tokens() -> None:
    rl = RateLimiter()
    for _ in range(60):
        allowed, _ = rl.check("agent-key", "agent")
        if not allowed:
            break
    allowed, headers = rl.check("agent-key", "agent")
    assert allowed is False
    assert "Retry-After" in headers


def test_different_keys_independent() -> None:
    rl = RateLimiter()
    for _ in range(60):
        rl.check("key-a", "agent")
    _, _ = rl.check("key-a", "agent")
    allowed, _ = rl.check("key-b", "agent")
    assert allowed is True


def test_reset_bucket() -> None:
    rl = RateLimiter()
    for _ in range(60):
        rl.check("reset-key", "agent")
    rl.reset("reset-key")
    allowed, _ = rl.check("reset-key", "agent")
    assert allowed is True


def test_admin_high_limit() -> None:
    rl = RateLimiter()
    for _ in range(200):
        allowed, _ = rl.check("admin-key", "admin")
        assert allowed is True
