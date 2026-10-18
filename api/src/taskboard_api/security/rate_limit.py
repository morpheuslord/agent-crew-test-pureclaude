"""Fixed-window rate limiting with Redis and an in-process fallback."""

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_MAX_MEMORY_KEYS = 50_000


def limiter_key(scope: str, subject: str) -> str:
    """Build a key without storing the raw subject (e.g. an email address) in Redis."""
    digest = hashlib.sha256(subject.lower().encode()).hexdigest()[:32]
    return f"tb:rl:{scope}:{digest}"


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Count one attempt. Return ``None`` if allowed, else seconds until the window resets."""
        ...


class InMemoryRateLimiter:
    """Per-process counters. Used in tests and as the fallback when Redis is unavailable."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        now = self._clock()
        with self._lock:
            if len(self._windows) > _MAX_MEMORY_KEYS:
                self._windows = {k: v for k, v in self._windows.items() if v[0] > now}
            reset_at, count = self._windows.get(key, (0.0, 0))
            if reset_at <= now:
                reset_at, count = now + window_seconds, 0
            count += 1
            self._windows[key] = (reset_at, count)
            if count > limit:
                return max(1, int(reset_at - now))
            return None


class RedisRateLimiter:
    def __init__(self, client: Redis) -> None:
        self._client = client

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        pipe.ttl(key)
        count, _, ttl = pipe.execute()
        if int(count) > limit:
            return max(1, int(ttl))
        return None


class FallbackRateLimiter:
    """Use the primary limiter, and the fallback whenever the primary raises a Redis error."""

    def __init__(self, primary: RateLimiter, fallback: RateLimiter) -> None:
        self._primary = primary
        self._fallback = fallback

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        try:
            return self._primary.hit(key, limit, window_seconds)
        except RedisError:
            logger.warning("rate limiter: Redis unavailable, using in-process counters")
            return self._fallback.hit(key, limit, window_seconds)
