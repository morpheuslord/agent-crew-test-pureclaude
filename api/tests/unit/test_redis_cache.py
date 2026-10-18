from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Any, cast

from redis.exceptions import ConnectionError as RedisConnectionError

from taskboard_api.cache.redis_cache import RedisCache

if TYPE_CHECKING:
    from redis import Redis


class FlakyRedis:
    """Enough of the redis-py client for RedisCache, with an on/off switch."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.down = False
        self.calls = 0

    def _check(self) -> None:
        self.calls += 1
        if self.down:
            raise RedisConnectionError("connection refused")

    def ping(self) -> bool:
        self._check()
        return True

    def get(self, key: str) -> Any:
        self._check()
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int) -> None:
        self._check()
        self.data[key] = value

    def delete(self, *keys: str) -> None:
        self._check()
        for key in keys:
            self.data.pop(key, None)

    def smembers(self, key: str) -> AbstractSet[str]:
        self._check()
        return set(self.data.get(key, set()))

    def pipeline(self) -> "FlakyRedis":
        return self

    def sadd(self, key: str, member: str) -> None:
        self.data.setdefault(key, set()).add(member)

    def expire(self, key: str, seconds: int) -> None:
        return None

    def execute(self) -> None:
        self._check()


class Ticker:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_roundtrip_and_index_invalidation() -> None:
    fake = FlakyRedis()
    cache = RedisCache(cast("Redis", fake), retry_after_seconds=30)
    cache.set("a", "1", 60)
    cache.add_to_index("idx", "a", 60)
    assert cache.get("a") == "1"
    fake.data["b"] = 7
    assert cache.get("b") == "7"
    cache.invalidate_index("idx")
    assert cache.get("a") is None
    assert "idx" not in fake.data
    cache.delete("b")
    assert cache.available()


def test_errors_are_counted_and_redis_is_bypassed_for_a_while() -> None:
    fake = FlakyRedis()
    ticker = Ticker()
    cache = RedisCache(cast("Redis", fake), retry_after_seconds=30, clock=ticker)
    fake.down = True
    assert cache.get("a") is None
    calls = fake.calls
    cache.set("a", "1", 60)
    cache.delete("a")
    cache.add_to_index("i", "a", 60)
    cache.invalidate_index("i")
    assert fake.calls == calls
    assert not cache.available()
    assert cache.counters().errors == 1
    fake.down = False
    ticker.now += 31
    assert cache.available()
    cache.set("a", "1", 60)
    assert cache.get("a") == "1"
