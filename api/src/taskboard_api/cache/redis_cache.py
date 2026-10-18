"""Redis cache backend that degrades to "always miss" while Redis is unavailable."""

import logging
import threading
import time
from collections.abc import Callable

from redis import Redis
from redis.exceptions import RedisError

from taskboard_api.cache.interface import Cache

logger = logging.getLogger(__name__)


class RedisCache(Cache):
    """Cache-aside storage in Redis.

    Any Redis error is logged, counted, and treated as a miss (reads) or skipped (writes). After an
    error the backend is bypassed for ``retry_after_seconds`` so requests do not each wait for a
    socket timeout while Redis is down.
    """

    backend_name = "redis"

    def __init__(
        self,
        client: "Redis",
        *,
        retry_after_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._client = client
        self._retry_after = retry_after_seconds
        self._clock = clock
        self._state_lock = threading.Lock()
        self._down_until = 0.0

    def available(self) -> bool:
        if self._bypassed():
            return False
        return self._guard("ping", lambda: bool(self._client.ping()), default=False)

    def _get(self, key: str) -> str | None:
        def read() -> str | None:
            value = self._client.get(key)
            return value if isinstance(value, str) or value is None else str(value)

        return self._guard("get", read, default=None)

    def _set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._guard("set", lambda: self._client.set(key, value, ex=ttl_seconds), default=None)

    def _delete(self, keys: tuple[str, ...]) -> None:
        self._guard("delete", lambda: self._client.delete(*keys), default=None)

    def _add_to_index(self, index_key: str, member: str, ttl_seconds: int) -> None:
        def write() -> None:
            pipe = self._client.pipeline()
            pipe.sadd(index_key, member)
            # The index must outlive the entries it lists.
            pipe.expire(index_key, ttl_seconds * 2)
            pipe.execute()

        self._guard("index", write, default=None)

    def _invalidate_index(self, index_key: str) -> None:
        def invalidate() -> None:
            members = self._client.smembers(index_key)
            self._client.delete(*{str(member) for member in members}, index_key)

        self._guard("invalidate", invalidate, default=None)

    def _bypassed(self) -> bool:
        with self._state_lock:
            return self._clock() < self._down_until

    def _guard[T](self, operation: str, call: Callable[[], T], *, default: T) -> T:
        if self._bypassed():
            return default
        try:
            return call()
        except RedisError as exc:
            self.record_error()
            with self._state_lock:
                self._down_until = self._clock() + self._retry_after
            logger.warning(
                "cache: Redis unavailable, continuing without cache",
                extra={"operation": operation, "error_type": type(exc).__name__},
            )
            return default
