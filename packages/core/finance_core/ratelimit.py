"""Token bucket rate limiter for API endpoints."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class BucketConfig:
    max_tokens: float
    refill_rate: float  # tokens per second


ROLE_LIMITS: dict[str, BucketConfig] = {
    "admin": BucketConfig(max_tokens=1000, refill_rate=100),
    "agent": BucketConfig(max_tokens=60, refill_rate=1),
    "viewer": BucketConfig(max_tokens=120, refill_rate=2),
    "dashboard": BucketConfig(max_tokens=300, refill_rate=10),
}


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    config: BucketConfig


@dataclass
class RateLimiter:
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, key: str, role: str = "viewer") -> tuple[bool, dict[str, str]]:
        """
        Consume one token. Returns (allowed, headers).
        Headers include X-RateLimit-* for the response.
        """
        cfg = ROLE_LIMITS.get(role, ROLE_LIMITS["viewer"])
        now = time.monotonic()

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(
                    tokens=cfg.max_tokens,
                    last_refill=now,
                    config=cfg,
                )
                self._buckets[key] = bucket

            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                cfg.max_tokens,
                bucket.tokens + elapsed * cfg.refill_rate,
            )
            bucket.last_refill = now

            headers = {
                "X-RateLimit-Limit": str(int(cfg.max_tokens)),
                "X-RateLimit-Remaining": str(max(0, int(bucket.tokens) - 1)),
            }

            if bucket.tokens < 1:
                wait = (1 - bucket.tokens) / cfg.refill_rate
                headers["Retry-After"] = str(int(wait) + 1)
                return False, headers

            bucket.tokens -= 1
            return True, headers

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)


rate_limiter = RateLimiter()
