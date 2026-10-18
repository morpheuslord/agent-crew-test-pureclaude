import re

from sqlalchemy import text

from tests.integration.conftest import PASSWORD, SERVICE_TOKEN, Harness, signup


def test_requests_without_service_token_are_rejected(harness: Harness) -> None:
    response = harness.client.get("/api/v1/auth/me", headers={"X-Service-Token": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_endpoints_need_no_token(harness: Harness) -> None:
    assert harness.client.get("/healthz", headers={"X-Service-Token": ""}).json() == {
        "status": "ok"
    }
    ready = harness.client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"


def test_register_login_me_logout(harness: Harness) -> None:
    headers = signup(harness.client, "ada")
    me = harness.client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["role"] == "member"
    assert "password_hash" not in me.json()
    assert me.headers["x-request-id"]
    assert harness.client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert harness.client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_request_id_is_propagated(harness: Harness) -> None:
    response = harness.client.get("/healthz", headers={"X-Request-Id": "req-abc-1"})
    assert response.headers["x-request-id"] == "req-abc-1"


def test_validation_errors_do_not_echo_input(harness: Harness) -> None:
    response = harness.client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "display_name": "", "password": "s3cr3t"},
    )
    assert response.status_code == 422
    body = response.text
    assert "s3cr3t" not in body
    assert set(response.json()["error"]["fields"]) == {"email", "display_name", "password"}


def test_register_rejects_extra_fields_like_role(harness: Harness) -> None:
    response = harness.client.post(
        "/api/v1/auth/register",
        json={
            "email": "eve@example.com",
            "display_name": "Eve",
            "password": PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_duplicate_registration_conflicts(harness: Harness) -> None:
    signup(harness.client, "ada")
    response = harness.client.post(
        "/api/v1/auth/register",
        json={"email": "ADA@example.com", "display_name": "Ada", "password": PASSWORD},
    )
    assert response.status_code == 409


def test_bad_credentials_and_malformed_authorization(harness: Harness) -> None:
    signup(harness.client, "ada")
    wrong = harness.client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope nope nope"}
    )
    unknown = harness.client.post(
        "/api/v1/auth/login", json={"email": "who@example.com", "password": "nope nope nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    for header in ["Basic abc", "Bearer", "Bearer not-a-token"]:
        response = harness.client.get("/api/v1/auth/me", headers={"Authorization": header})
        assert response.status_code == 401


def test_password_change_and_reset_flow_via_outbox(harness: Harness) -> None:
    headers = signup(harness.client, "ada")
    changed = harness.client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "second password 2"},
    )
    assert changed.status_code == 204
    forgot = harness.client.post("/api/v1/auth/password/forgot", json={"email": "ada@example.com"})
    assert forgot.status_code == 202
    unknown = harness.client.post(
        "/api/v1/auth/password/forgot", json={"email": "ghost@example.com"}
    )
    assert unknown.status_code == 202
    assert unknown.json() == forgot.json()
    with harness.container.engine.connect() as connection:
        body = connection.execute(
            text("SELECT body FROM outbox WHERE to_address = 'ada@example.com'")
        ).scalar_one()
    assert "http://ui.test:3000/reset-password?token=" in body
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match is not None
    reset = harness.client.post(
        "/api/v1/auth/password/reset",
        json={"token": match.group(1), "new_password": "third password 3"},
    )
    assert reset.status_code == 204
    assert harness.client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login = harness.client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "third password 3"}
    )
    assert login.status_code == 200
    again = harness.client.post(
        "/api/v1/auth/password/reset",
        json={"token": match.group(1), "new_password": "fourth password 4"},
    )
    assert again.status_code == 422


def test_login_rate_limit_returns_retry_after(harness: Harness) -> None:
    signup(harness.client, "ada")
    statuses = []
    for _ in range(11):
        response = harness.client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": "wrong password!"},
        )
        statuses.append(response.status_code)
    assert statuses[-1] == 429
    assert int(response.headers["retry-after"]) > 0


def test_openapi_document_is_served(harness: Harness) -> None:
    document = harness.client.get("/api/v1/openapi.json").json()
    assert "/api/v1/search/tasks" in document["paths"]
    assert SERVICE_TOKEN not in str(document)
