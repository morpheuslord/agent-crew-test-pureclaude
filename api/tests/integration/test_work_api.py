import csv
import io
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import Harness, signup


def _team_with_project(client: TestClient, owner: dict[str, str]) -> tuple[str, str]:
    team = client.post("/api/v1/teams", headers=owner, json={"name": "Core"})
    assert team.status_code == 201, team.text
    project = client.post(
        f"/api/v1/teams/{team.json()['id']}/projects",
        headers=owner,
        json={"name": "Roadmap", "webhook_url": "https://hooks.example.com/in"},
    )
    assert project.status_code == 201, project.text
    return team.json()["id"], project.json()["id"]


def _task(client: TestClient, headers: dict[str, str], project_id: str, **body: Any) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/tasks", headers=headers, json={"title": "T", **body}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_teams_projects_and_object_level_authorisation(harness: Harness) -> None:
    client = harness.client
    owner = signup(client, "olive")
    bob = signup(client, "bob")
    mallory = signup(client, "mallory")
    team_id, project_id = _team_with_project(client, owner)
    assert client.get(f"/api/v1/teams/{team_id}", headers=mallory).status_code == 404
    assert client.get(f"/api/v1/projects/{project_id}", headers=mallory).status_code == 404
    added = client.post(
        f"/api/v1/teams/{team_id}/members", headers=owner, json={"email": "bob@example.com"}
    )
    assert added.status_code == 201
    forbidden = client.post(
        f"/api/v1/teams/{team_id}/members", headers=bob, json={"email": "mallory@example.com"}
    )
    assert forbidden.status_code == 403
    assert [t["id"] for t in client.get("/api/v1/teams", headers=bob).json()] == [team_id]
    assert [p["id"] for p in client.get("/api/v1/projects", headers=bob).json()] == [project_id]
    detail = client.get(f"/api/v1/projects/{project_id}", headers=bob).json()
    assert detail["webhook_secret"] is None
    assert len(detail["members"]) == 2
    projects = client.get(f"/api/v1/teams/{team_id}/projects", headers=bob).json()
    assert [p["name"] for p in projects] == ["Roadmap"]
    member_id = added.json()["user_id"]
    removed = client.delete(f"/api/v1/teams/{team_id}/members/{member_id}", headers=owner)
    assert removed.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}", headers=bob).status_code == 404


def test_task_lifecycle_comments_activity_and_webhook(harness: Harness) -> None:
    client = harness.client
    owner = signup(client, "olive")
    _, project_id = _team_with_project(client, owner)
    task_id = _task(
        client, owner, project_id, title="Ship it", description="**bold**", labels=["Release"]
    )
    patched = client.patch(f"/api/v1/tasks/{task_id}", headers=owner, json={"status": "done"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"
    [delivery] = harness.notifier.deliveries
    assert delivery.payload["new_status"] == "done"
    assert delivery.payload["old_status"] == "todo"
    comment = client.post(
        f"/api/v1/tasks/{task_id}/comments", headers=owner, json={"body": "Looks good"}
    )
    assert comment.status_code == 201
    comment_id = comment.json()["id"]
    edited = client.patch(f"/api/v1/comments/{comment_id}", headers=owner, json={"body": "Edit"})
    assert edited.json()["body"] == "Edit"
    listed = client.get(f"/api/v1/tasks/{task_id}/comments", headers=owner).json()
    assert [c["body"] for c in listed] == ["Edit"]
    assert client.delete(f"/api/v1/comments/{comment_id}", headers=owner).status_code == 204
    feed = client.get(f"/api/v1/projects/{project_id}/activity", headers=owner).json()
    assert [item["event_type"] for item in feed["items"]] == [
        "comment.added",
        "task.status_changed",
        "task.created",
    ]
    assert client.get(f"/api/v1/tasks/{task_id}", headers=owner).json()["labels"] == ["release"]
    assert client.delete(f"/api/v1/tasks/{task_id}", headers=owner).status_code == 204
    assert client.get(f"/api/v1/tasks/{task_id}", headers=owner).status_code == 404


def test_task_list_filters_sort_and_rejects_unknown_sort(harness: Harness) -> None:
    client = harness.client
    owner = signup(client, "olive")
    _, project_id = _team_with_project(client, owner)
    _task(client, owner, project_id, title="b", priority="high", labels=["x"])
    _task(client, owner, project_id, title="a", priority="low", due_date="2026-11-01")
    _task(client, owner, project_id, title="c 100%_done", priority="medium", status="done")
    url = f"/api/v1/projects/{project_id}/tasks"
    by_priority = client.get(url, headers=owner, params={"sort": "priority", "order": "desc"})
    assert [t["title"] for t in by_priority.json()["items"]] == ["b", "c 100%_done", "a"]
    done = client.get(url, headers=owner, params={"status": "done"}).json()
    assert done["total"] == 1
    for bad in [{"sort": "title; DROP TABLE tasks"}, {"order": "sideways"}, {"page_size": 101}]:
        assert client.get(url, headers=owner, params=bad).status_code == 422
    wildcard = client.get("/api/v1/search/tasks", headers=owner, params={"q": "%"}).json()
    assert [t["title"] for t in wildcard["items"]] == ["c 100%_done"]
    underscore = client.get("/api/v1/search/tasks", headers=owner, params={"q": "_"}).json()
    assert underscore["total"] == 1
    labelled = client.get("/api/v1/search/tasks", headers=owner, params={"label": "X"}).json()
    assert [t["title"] for t in labelled["items"]] == ["b"]
    due = client.get(
        "/api/v1/search/tasks",
        headers=owner,
        params={"due_before": "2026-12-01", "sort": "title", "order": "asc"},
    ).json()
    assert [t["title"] for t in due["items"]] == ["a"]
    paged = client.get(
        "/api/v1/search/tasks",
        headers=owner,
        params={"sort": "title", "order": "asc", "page": 2, "page_size": 2},
    ).json()
    assert (paged["total"], [t["title"] for t in paged["items"]]) == (3, ["c 100%_done"])
    other = signup(client, "eve")
    assert client.get("/api/v1/search/tasks", headers=other).json()["total"] == 0


def test_attachments_upload_download_and_limits(harness: Harness) -> None:
    client = harness.client
    owner = signup(client, "olive")
    _, project_id = _team_with_project(client, owner)
    task_id = _task(client, owner, project_id)
    upload = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        headers=owner,
        files={"file": ("<script>x.html", b"<script>alert(1)</script>", "text/html")},
    )
    assert upload.status_code == 201, upload.text
    attachment = upload.json()
    listed = client.get(f"/api/v1/tasks/{task_id}/attachments", headers=owner).json()
    assert [a["id"] for a in listed] == [attachment["id"]]
    download = client.get(f"/api/v1/attachments/{attachment['id']}/download", headers=owner)
    assert download.status_code == 200
    assert download.content == b"<script>alert(1)</script>"
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["x-content-type-options"] == "nosniff"
    disposition = download.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="_script_x.html"')
    too_big = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        headers=owner,
        files={"file": ("big.bin", b"x" * 1025, "application/octet-stream")},
    )
    assert too_big.status_code == 413
    huge = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        headers={**owner, "Content-Type": "application/octet-stream"},
        content=b"x" * (3 * 1024 * 1024),
    )
    assert huge.status_code == 413
    mallory = signup(client, "mallory")
    stolen = client.get(f"/api/v1/attachments/{attachment['id']}/download", headers=mallory)
    assert stolen.status_code == 404


def test_csv_export_and_archive(harness: Harness) -> None:
    client = harness.client
    owner = signup(client, "olive")
    _, project_id = _team_with_project(client, owner)
    _task(client, owner, project_id, title="=cmd|' /C calc'!A0")
    export = client.get(f"/api/v1/projects/{project_id}/export.csv", headers=owner)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "Roadmap-tasks.csv" in export.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(export.text)))
    assert rows[1][1].startswith("'=")
    archived = client.post(f"/api/v1/projects/{project_id}/archive", headers=owner)
    assert archived.json()["archived"] is True
    blocked = client.post(
        f"/api/v1/projects/{project_id}/tasks", headers=owner, json={"title": "late"}
    )
    assert blocked.status_code == 409
    renamed = client.patch(f"/api/v1/projects/{project_id}", headers=owner, json={"name": "New"})
    assert renamed.status_code == 409


def test_admin_endpoints(harness: Harness) -> None:
    client = harness.client
    member = signup(client, "bob")
    assert client.get("/api/v1/admin/users", headers=member).status_code == 403
    admin = signup(client, "root")
    with harness.container.engine.begin() as connection:
        connection.execute(text("UPDATE users SET role = 'admin' WHERE email = 'root@example.com'"))
    users = client.get("/api/v1/admin/users", headers=admin, params={"q": "bob"}).json()
    [bob] = users["items"]
    deactivated = client.patch(
        f"/api/v1/admin/users/{bob['id']}", headers=admin, json={"is_active": False}
    )
    assert deactivated.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=member).status_code == 401
    assert client.get("/api/v1/admin/activity", headers=admin).status_code == 200
    stats = client.get("/api/v1/admin/cache-stats", headers=admin).json()
    assert set(stats) == {"backend", "hits", "misses", "errors", "available"}
    invalid_role = client.patch(
        f"/api/v1/admin/users/{bob['id']}", headers=admin, json={"role": "superuser"}
    )
    assert invalid_role.status_code == 422
