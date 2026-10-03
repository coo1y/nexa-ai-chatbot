"""In-memory sliding-window rate limiter (per anonymous client and per IP).

Sufficient for a single instance. For horizontal scaling swap in a Redis-backed
implementation with the same interface.
"""

import time
from collections import defaultdict, deque

from app.core.errors import RateLimited


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise RateLimited("You're sending requests too quickly. Please wait a moment and try again.")
        hits.append(now)
        if len(self._hits) > 50_000:  # bound memory under abuse
            self._evict(now, window_seconds)

    def _evict(self, now: float, window_seconds: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > window_seconds]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()
