"""Cache backends that need no external service."""

import threading
import time
from collections.abc import Callable

from taskboard_api.cache.interface import Cache


class NullCache(Cache):
    """Caches nothing. Every lookup is a miss."""

    backend_name = "null"

    def available(self) -> bool:
        return True

    def _get(self, key: str) -> str | None:
        return None

    def _set(self, key: str, value: str, ttl_seconds: int) -> None:
        return None

    def _delete(self, keys: tuple[str, ...]) -> None:
        return None

    def _add_to_index(self, index_key: str, member: str, ttl_seconds: int) -> None:
        return None

    def _invalidate_index(self, index_key: str) -> None:
        return None


class InMemoryCache(Cache):
    """A thread-safe dictionary with expiry, for unit tests and single-process use."""

    backend_name = "memory"

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__()
        self._clock = clock
        self._data_lock = threading.Lock()
        self._values: dict[str, tuple[float, str]] = {}
        self._indexes: dict[str, set[str]] = {}

    def available(self) -> bool:
        return True

    def live_keys(self) -> set[str]:
        """Live keys, for assertions in tests."""
        now = self._clock()
        with self._data_lock:
            return {key for key, (expires, _) in self._values.items() if expires > now}

    def _get(self, key: str) -> str | None:
        with self._data_lock:
            entry = self._values.get(key)
            if entry is None:
                return None
            expires, value = entry
            if expires <= self._clock():
                del self._values[key]
                return None
            return value

    def _set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._data_lock:
            self._values[key] = (self._clock() + ttl_seconds, value)

    def _delete(self, keys: tuple[str, ...]) -> None:
        with self._data_lock:
            for key in keys:
                self._values.pop(key, None)

    def _add_to_index(self, index_key: str, member: str, ttl_seconds: int) -> None:
        with self._data_lock:
            self._indexes.setdefault(index_key, set()).add(member)

    def _invalidate_index(self, index_key: str) -> None:
        with self._data_lock:
            for member in self._indexes.pop(index_key, set()):
                self._values.pop(member, None)
