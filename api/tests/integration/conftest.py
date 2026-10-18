"""Integration tests against real PostgreSQL and Redis.

Set ``TEST_DATABASE_URL`` (a database the tests may wipe) and ``TEST_REDIS_URL`` (a Redis database
the tests may flush). The schema is created with the Alembic migrations, not ``create_all``.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from taskboard_api.api.app import create_app
from taskboard_api.cache.interface import Cache
from taskboard_api.cache.memory import NullCache
from taskboard_api.cli import alembic_config
from taskboard_api.composition import Container
from taskboard_api.config import Settings
from taskboard_api.models import Base
from taskboard_api.security.passwords import Argon2PasswordHasher
from taskboard_api.storage.local import LocalFileStorage
from tests.fakes import RecordingNotifier

SERVICE_TOKEN = "integration-service-token-0123456789abcdef"
PASSWORD = "integration password 1"


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def redis_url() -> str:
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL is not set")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(database_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clean_engine(engine: Engine) -> Engine:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    return engine


def make_settings(database_url: str, tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": database_url,
        "service_token": SERVICE_TOKEN,
        "public_ui_url": "http://ui.test:3000",
        "storage_local_path": str(tmp_path / "attachments"),
        "argon2_time_cost": 1,
        "argon2_memory_cost_kib": 8,
        "max_upload_bytes": 1024,
    }
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.fixture
def cache_backend() -> Cache:
    """Overridden in the cache tests to use real Redis."""
    return NullCache()


@dataclass
class Harness:
    client: TestClient
    container: Container
    notifier: RecordingNotifier


@pytest.fixture
def harness(
    database_url: str, clean_engine: Engine, tmp_path: Path, cache_backend: Cache
) -> Iterator[Harness]:
    settings = make_settings(database_url, tmp_path)
    notifier = RecordingNotifier()
    container = Container(
        settings,
        engine=clean_engine,
        cache=cache_backend,
        storage=LocalFileStorage(tmp_path / "attachments"),
        notifier=notifier,
        hasher=Argon2PasswordHasher(1, 8),
    )
    app = create_app(settings, container)
    with TestClient(app, headers={"X-Service-Token": SERVICE_TOKEN}) as client:
        yield Harness(client, container, notifier)


def signup(client: TestClient, name: str) -> dict[str, str]:
    """Register and log in; return headers that authenticate as that user."""
    email = f"{name}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name.title(), "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}
