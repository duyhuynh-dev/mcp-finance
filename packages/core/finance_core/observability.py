"""Observability: structured logging, request metrics, tracing."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("finance_stack")


@dataclass
class RequestMetrics:
    """Thread-safe request metrics collector."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    total_requests: int = 0
    total_errors: int = 0
    status_counts: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    endpoint_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    endpoint_latencies: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _start_time: float = field(default_factory=time.monotonic)

    def record(
        self, path: str, status: int, latency_ms: float
    ) -> None:
        with self._lock:
            self.total_requests += 1
            if status >= 400:
                self.total_errors += 1
            self.status_counts[status] += 1
            self.endpoint_counts[path] += 1
            lats = self.endpoint_latencies[path]
            lats.append(latency_ms)
            if len(lats) > 500:
                self.endpoint_latencies[path] = lats[-200:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            uptime = time.monotonic() - self._start_time
            top_endpoints = sorted(
                self.endpoint_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:15]

            latency_stats: dict[str, dict[str, float]] = {}
            for path, lats in self.endpoint_latencies.items():
                if not lats:
                    continue
                s = sorted(lats)
                latency_stats[path] = {
                    "count": len(s),
                    "avg_ms": round(sum(s) / len(s), 2),
                    "p50_ms": round(s[len(s) // 2], 2),
                    "p95_ms": round(s[int(len(s) * 0.95)], 2),
                    "p99_ms": round(s[int(len(s) * 0.99)], 2),
                    "max_ms": round(s[-1], 2),
                }

            return {
                "uptime_seconds": round(uptime, 1),
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "error_rate": (
                    round(self.total_errors / self.total_requests, 4)
                    if self.total_requests
                    else 0
                ),
                "requests_per_second": (
                    round(self.total_requests / uptime, 2)
                    if uptime > 0
                    else 0
                ),
                "status_codes": dict(self.status_counts),
                "top_endpoints": [
                    {"path": p, "count": c} for p, c in top_endpoints
                ],
                "latency": latency_stats,
            }


def generate_request_id() -> str:
    return str(uuid.uuid4())[:8]


metrics = RequestMetrics()
