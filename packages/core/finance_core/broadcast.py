"""Thread-safe event bus for real-time WebSocket broadcasting."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any


class EventBus:
    """Pub/sub bus safe for cross-thread use (sync publishers, async consumers)."""

    def __init__(self) -> None:
        self._subscribers: list[deque[dict[str, Any]]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> deque[dict[str, Any]]:
        d: deque[dict[str, Any]] = deque(maxlen=500)
        with self._lock:
            self._subscribers.append(d)
        return d

    def unsubscribe(self, d: deque[dict[str, Any]]) -> None:
        with self._lock:
            try:
                self._subscribers.remove(d)
            except ValueError:
                pass

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for d in subs:
            d.append(event)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)


event_bus = EventBus()
