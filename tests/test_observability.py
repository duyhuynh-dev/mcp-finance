"""Tests for observability module."""

from __future__ import annotations

from finance_core.observability import RequestMetrics, generate_request_id


def test_request_id_format() -> None:
    rid = generate_request_id()
    assert len(rid) == 8
    assert rid != generate_request_id()


def test_metrics_record() -> None:
    m = RequestMetrics()
    m.record("/api/portfolio", 200, 5.0)
    m.record("/api/portfolio", 200, 10.0)
    m.record("/api/place-order", 400, 3.0)

    snap = m.snapshot()
    assert snap["total_requests"] == 3
    assert snap["total_errors"] == 1
    assert snap["error_rate"] > 0
    assert snap["requests_per_second"] > 0
    assert "status_codes" in snap
    assert snap["status_codes"][200] == 2
    assert snap["status_codes"][400] == 1


def test_latency_stats() -> None:
    m = RequestMetrics()
    for i in range(100):
        m.record("/api/test", 200, float(i))

    snap = m.snapshot()
    lat = snap["latency"]["/api/test"]
    assert lat["count"] == 100
    assert lat["avg_ms"] > 0
    assert lat["p50_ms"] > 0
    assert lat["p95_ms"] > lat["p50_ms"]
    assert lat["max_ms"] == 99.0


def test_top_endpoints() -> None:
    m = RequestMetrics()
    for _ in range(50):
        m.record("/api/a", 200, 1.0)
    for _ in range(30):
        m.record("/api/b", 200, 1.0)
    for _ in range(10):
        m.record("/api/c", 200, 1.0)

    snap = m.snapshot()
    top = snap["top_endpoints"]
    assert top[0]["path"] == "/api/a"
    assert top[0]["count"] == 50
