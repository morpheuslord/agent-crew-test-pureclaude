from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from taskboard_api.api.app import create_app
from taskboard_api.cli import main
from taskboard_api.composition import Container
from taskboard_api.security.passwords import Argon2PasswordHasher
from taskboard_api.storage.local import LocalFileStorage
from tests.fakes import RecordingNotifier
from tests.integration.conftest import PASSWORD, SERVICE_TOKEN, Harness, make_settings, signup


def test_cli_migrate_and_create_admin(
    monkeypatch: pytest.MonkeyPatch, database_url: str, clean_engine: Engine, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SERVICE_TOKEN", SERVICE_TOKEN)
    monkeypatch.setenv("PUBLIC_UI_URL", "http://ui.test:3000")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("ARGON2_MEMORY_COST_KIB", "8")
    monkeypatch.setenv("ARGON2_TIME_COST", "1")
    assert main(["migrate"]) == 0
    monkeypatch.setenv("ADMIN_EMAIL", "short")
    assert main(["create-admin"]) == 2
    monkeypatch.setenv("ADMIN_EMAIL", "Admin@Example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    assert main(["create-admin"]) == 0
    assert main(["create-admin"]) == 0
    with clean_engine.connect() as connection:
        role = connection.execute(
            text("SELECT role FROM users WHERE email = 'admin@example.com'")
        ).scalar_one()
    assert role == "admin"


def test_invalid_client_ip_header_falls_back(harness: Harness) -> None:
    response = harness.client.post(
        "/api/v1/auth/register",
        headers={"X-Client-Ip": "not-an-ip"},
        json={"email": "ip@example.com", "display_name": "Ip", "password": PASSWORD},
    )
    assert response.status_code == 201


def test_chunked_upload_over_limit_is_rejected_with_413(harness: Harness) -> None:
    owner = signup(harness.client, "olive")

    def chunks() -> Iterator[bytes]:
        for _ in range(64):
            yield b"x" * 65_536

    response = harness.client.post(
        "/api/v1/auth/login",
        headers={**owner, "Content-Type": "application/json"},
        content=chunks(),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_readiness_reports_database_outage_and_errors_are_generic(
    database_url: str, tmp_path: Path
) -> None:
    settings = make_settings(database_url, tmp_path)
    broken = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )
    container = Container(
        settings,
        engine=broken,
        storage=LocalFileStorage(tmp_path),
        notifier=RecordingNotifier(),
        hasher=Argon2PasswordHasher(1, 8),
    )
    app = create_app(settings, container)

    def boom() -> None:
        raise RuntimeError("secret internal detail")

    app.add_api_route("/boom", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 503
        assert ready.json()["checks"]["database"] == "unavailable"
        error = client.get("/boom")
        assert error.status_code == 500
        assert "secret internal detail" not in error.text
        missing = client.get("/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "http_error"
