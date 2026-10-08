from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from .errors import too_many


class RateLimiter:
    """Sliding-window limiter, per process. On AWS the API Gateway stage throttle is the real control."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] < now - window_s:
                q.popleft()
            if len(q) >= limit:
                raise too_many("Too many attempts. Please wait a moment and try again.", retry_after=window_s)
            q.append(now)
