from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import Engine, text

from taskboard_api.api.app import create_app
from taskboard_api.composition import Container
from tests.integration.conftest import SERVICE_TOKEN, Harness, build_harness, make_settings, signup


@pytest.fixture
def redis_client(clean_redis: str) -> Iterator[Redis]:
    client = Redis.from_url(clean_redis, decode_responses=True)
    yield client
    client.close()


def _counters(harness: Harness) -> tuple[int, int]:
    counters = harness.container.cache_backend.counters()
    return counters.hits, counters.misses


def test_backend_is_redis(harness: Harness) -> None:
    assert harness.container.cache_backend.backend_name == "redis"
    assert harness.client.get("/readyz").json()["checks"]["cache"] == "ok"


def test_task_lists_are_cached_per_filter_and_invalidated_on_write(
    harness: Harness, redis_client: Redis
) -> None:
    client = harness.client
    owner = signup(client, "olive")
    team = client.post("/api/v1/teams", headers=owner, json={"name": "Core"}).json()
    project = client.post(
        f"/api/v1/teams/{team['id']}/projects", headers=owner, json={"name": "P"}
    ).json()
    url = f"/api/v1/projects/{project['id']}/tasks"
    client.post(url, headers=owner, json={"title": "one"})
    before = _counters(harness)
    first = client.get(url, headers=owner, params={"status": "todo"}).json()
    second = client.get(url, headers=owner, params={"status": "todo"}).json()
    other_filter = client.get(url, headers=owner, params={"status": "done"}).json()
    hits, misses = _counters(harness)
    assert first == second
    assert other_filter["total"] == 0
    assert (hits - before[0], misses - before[1]) == (1, 2)
    page_keys = [
        k for k in redis_client.keys(f"tb:project:{project['id']}:tasks:*") if "index" not in k
    ]
    assert len(page_keys) == 2
    assert all(redis_client.ttl(key) > 0 for key in page_keys)
    task = client.post(url, headers=owner, json={"title": "two"}).json()
    assert redis_client.keys(f"tb:project:{project['id']}:tasks:*") == []
    assert client.get(url, headers=owner, params={"status": "todo"}).json()["total"] == 2
    client.get(f"/api/v1/tasks/{task['id']}", headers=owner)
    assert redis_client.exists(f"tb:task:{task['id']}")
    client.patch(f"/api/v1/tasks/{task['id']}", headers=owner, json={"title": "renamed"})
    assert not redis_client.exists(f"tb:task:{task['id']}")
    assert client.get(f"/api/v1/tasks/{task['id']}", headers=owner).json()["title"] == "renamed"


def test_profile_and_team_lists_are_invalidated(harness: Harness, redis_client: Redis) -> None:
    client = harness.client
    member = signup(client, "bob")
    owner = signup(client, "olive")
    me = client.get("/api/v1/auth/me", headers=member).json()
    assert redis_client.exists(f"tb:user:{me['id']}:profile")
    assert client.get("/api/v1/teams", headers=member).json() == []
    team = client.post("/api/v1/teams", headers=owner, json={"name": "Core"}).json()
    client.post(
        f"/api/v1/teams/{team['id']}/members", headers=owner, json={"email": "bob@example.com"}
    )
    assert [t["id"] for t in client.get("/api/v1/teams", headers=member).json()] == [team["id"]]
    with harness.container.engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET role = 'admin' WHERE email = 'olive@example.com'")
        )
    client.patch(f"/api/v1/admin/users/{me['id']}", headers=owner, json={"role": "admin"})
    assert not redis_client.exists(f"tb:user:{me['id']}:profile")
    assert client.get("/api/v1/auth/me", headers=member).json()["role"] == "admin"
    stats = client.get("/api/v1/admin/cache-stats", headers=owner).json()
    assert stats["backend"] == "redis"
    assert stats["hits"] >= 0
    assert stats["misses"] > 0


def test_rate_limit_counters_live_in_redis_without_emails(
    harness: Harness, redis_client: Redis
) -> None:
    signup(harness.client, "ada")
    keys = redis_client.keys("tb:rl:*")
    assert keys
    assert not any("ada" in key for key in keys)


def test_api_keeps_working_when_redis_is_down(
    database_url: str, clean_engine: Engine, tmp_path: Path
) -> None:
    settings = make_settings(database_url, tmp_path, "redis://127.0.0.1:1/0")
    container: Container = build_harness(settings, clean_engine, tmp_path)
    app = create_app(settings, container)
    with TestClient(app, headers={"X-Service-Token": SERVICE_TOKEN}) as client:
        owner = signup(client, "olive")
        team = client.post("/api/v1/teams", headers=owner, json={"name": "Core"})
        assert team.status_code == 201
        assert client.get("/api/v1/teams", headers=owner).json()[0]["name"] == "Core"
        ready = client.get("/readyz").json()
        assert ready["status"] == "ready"
        assert ready["checks"]["cache"] == "degraded"
    assert container.cache_backend.counters().errors >= 1
