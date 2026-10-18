import csv
import io

import pytest

from taskboard_api.domain.commands import AddMemberCommand, UpdateProjectCommand
from taskboard_api.domain.enums import ActivityType, Role
from taskboard_api.domain.queries import PageRequest
from taskboard_api.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from tests.unit.conftest import World


def test_owner_creates_project_and_member_lists_are_invalidated(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.join(team, bob)
    assert world.projects.list_my_projects(bob) == []
    project = world.project(owner, team, name="Launch")
    assert [p.id for p in world.projects.list_my_projects(bob)] == [project.id]
    assert [p.name for p in world.projects.list_team_projects(bob, team.id)] == ["Launch"]


def test_members_can_not_create_projects_but_admins_can(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.join(team, bob)
    with pytest.raises(PermissionDeniedError):
        world.project(bob, team)
    admin = world.user("root", role=Role.ADMIN)
    assert world.project(admin, team).can_manage


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.com/x",
        "ftp://hooks.example.com/x",
        "https://user:pw@hooks.example.com/x",
        "https:///nohost",
        "https://hooks.example.com:0/x",
        "not a url",
    ],
)
def test_unsafe_webhook_urls_are_rejected(world: World, url: str) -> None:
    owner = world.user("olive")
    team = world.team(owner)
    with pytest.raises(ValidationFailedError) as excinfo:
        world.project(owner, team, webhook_url=url)
    assert "webhook_url" in excinfo.value.fields


def test_webhook_secret_is_shown_only_to_managers(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.join(team, bob)
    project = world.project(owner, team, webhook_url="https://hooks.example.com/t")
    assert project.webhook_secret
    member_view = world.projects.get_project(bob, project.id)
    assert member_view.webhook_secret is None
    assert member_view.webhook_url is None
    assert not member_view.can_manage


def test_update_renames_and_clears_webhook(world: World) -> None:
    owner = world.user("olive")
    team = world.team(owner)
    project = world.project(owner, team, webhook_url="https://hooks.example.com/t")
    updated = world.projects.update_project(
        owner, project.id, UpdateProjectCommand.model_validate({"name": "Renamed"})
    )
    assert updated.name == "Renamed"
    assert updated.webhook_secret == project.webhook_secret
    cleared = world.projects.update_project(
        owner, project.id, UpdateProjectCommand.model_validate({"webhook_url": None})
    )
    assert cleared.webhook_url is None
    assert cleared.webhook_secret is None
    added = world.projects.update_project(
        owner,
        project.id,
        UpdateProjectCommand.model_validate({"webhook_url": "https://hooks.example.com/n"}),
    )
    assert added.webhook_secret


def test_archived_project_is_read_only(world: World) -> None:
    owner = world.user("olive")
    team = world.team(owner)
    project = world.project(owner, team)
    task = world.task(owner, project)
    archived = world.projects.archive_project(owner, project.id)
    assert archived.archived
    assert world.projects.archive_project(owner, project.id).archived
    with pytest.raises(ConflictError):
        world.task(owner, project)
    with pytest.raises(ConflictError):
        world.tasks.delete_task(owner, task.id)
    with pytest.raises(ConflictError):
        world.projects.update_project(owner, project.id, UpdateProjectCommand(name="x"))
    assert world.tasks.get_task(owner, task.id).id == task.id


def test_non_member_can_not_see_project(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner))
    with pytest.raises(NotFoundError):
        world.projects.get_project(world.user("mallory"), project.id)
    with pytest.raises(NotFoundError):
        world.projects.export_csv(world.user("eve"), project.id)


def test_project_feed_includes_task_and_membership_events(world: World) -> None:
    owner = world.user("olive")
    world.user("bob")
    team = world.team(owner)
    project = world.project(owner, team)
    other = world.project(owner, team, name="Other")
    world.task(owner, project, "Visible")
    world.task(owner, other, "Elsewhere")
    world.teams.add_member(owner, team.id, AddMemberCommand(email="bob@example.com"))
    feed = world.projects.project_activity(owner, project.id, PageRequest(1, 10))
    events = [item.event_type for item in feed.items]
    assert events == [ActivityType.MEMBER_ADDED, ActivityType.TASK_CREATED]
    assert feed.items[1].actor_name == "Olive"


def test_csv_export_neutralises_formulas(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner))
    world.task(owner, project, '=HYPERLINK("https://evil.example")', labels=["a", "b"])
    world.task(owner, project, "Normal", description="+1 and @me", assignee_id=str(owner.user_id))
    name, text = world.projects.export_csv(owner, project.id)
    rows = list(csv.reader(io.StringIO(text)))
    assert name == "Roadmap"
    assert rows[0][:3] == ["id", "title", "description"]
    assert rows[1][1].startswith("'=")
    assert rows[1][8] == "a;b"
    assert rows[2][2] == "'+1 and @me"
    assert rows[2][5:7] == ["Olive", "olive@example.com"]
