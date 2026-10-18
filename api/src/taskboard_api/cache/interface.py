"""Key-value cache interface with built-in hit/miss accounting."""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CacheCounters:
    hits: int
    misses: int
    errors: int


class Cache(ABC):
    """String cache. Subclasses implement the ``_``-prefixed primitives.

    ``get`` counts hits and misses and logs each lookup at debug level, so every backend reports
    the same statistics.
    """

    backend_name = "abstract"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._errors = 0

    def get(self, key: str) -> str | None:
        value = self._get(key)
        with self._lock:
            if value is None:
                self._misses += 1
            else:
                self._hits += 1
            hits, misses = self._hits, self._misses
        logger.debug(
            "cache %s",
            "miss" if value is None else "hit",
            extra={"cache_key": key, "cache_hits": hits, "cache_misses": misses},
        )
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._set(key, value, ttl_seconds)

    def delete(self, *keys: str) -> None:
        if keys:
            self._delete(keys)

    def add_to_index(self, index_key: str, member: str, ttl_seconds: int) -> None:
        """Remember ``member`` under ``index_key`` so it can be invalidated with the index."""
        self._add_to_index(index_key, member, ttl_seconds)

    def invalidate_index(self, index_key: str) -> None:
        """Delete every key registered under ``index_key`` and the index itself."""
        self._invalidate_index(index_key)

    def counters(self) -> CacheCounters:
        with self._lock:
            return CacheCounters(self._hits, self._misses, self._errors)

    def record_error(self) -> None:
        with self._lock:
            self._errors += 1

    @abstractmethod
    def available(self) -> bool:
        """Whether the backend is currently reachable."""

    @abstractmethod
    def _get(self, key: str) -> str | None: ...

    @abstractmethod
    def _set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    def _delete(self, keys: tuple[str, ...]) -> None: ...

    @abstractmethod
    def _add_to_index(self, index_key: str, member: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    def _invalidate_index(self, index_key: str) -> None: ...
