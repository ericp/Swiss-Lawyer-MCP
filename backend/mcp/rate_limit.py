"""Simple per-process rate limiter for the local single-user MCP server."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from backend.mcp.errors import RateLimitExceededError


class InMemoryRateLimiter:
    def __init__(self, *, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        self._events: dict[str, Deque[float]] = defaultdict(deque)

    def check(self, *, key: str, limit: int) -> None:
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > self._window_seconds:
            events.popleft()
        if len(events) >= limit:
            raise RateLimitExceededError()
        events.append(now)
