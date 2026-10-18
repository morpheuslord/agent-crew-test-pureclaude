import json
from datetime import date

import pytest

from taskboard_api.domain.commands import UpdateTaskCommand
from taskboard_api.domain.enums import ActivityType, Role, SortField, SortOrder, TaskStatus
from taskboard_api.domain.queries import PageRequest, TaskFilter
from taskboard_api.errors import NotFoundError, ValidationFailedError
from taskboard_api.models import Attachment
from taskboard_api.security.tokens import sign
from tests.unit.conftest import World


def _update(**fields: object) -> UpdateTaskCommand:
    return UpdateTaskCommand.model_validate(fields)


def test_create_task_requires_assignee_in_team(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner))
    outsider = world.user("mallory")
    with pytest.raises(ValidationFailedError) as excinfo:
        world.task(owner, project, assignee_id=str(outsider.user_id))
    assert "assignee_id" in excinfo.value.fields
    task = world.task(owner, project, labels=["UI", "ui", " Backend "])
    assert task.labels == ["ui", "backend"]
    assert world.uow.store.activity[-1].event_type is ActivityType.TASK_CREATED


def test_task_list_is_cached_per_filter_and_invalidated_by_writes(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner))
    world.task(owner, project, "One")
    todo = TaskFilter(status=TaskStatus.TODO)
    assert world.tasks.list_tasks(owner, project.id, todo).total == 1
    assert world.tasks.list_tasks(owner, project.id, todo).total == 1
    assert world.backend.counters().hits == 1
    world.task(owner, project, "Two")
    assert world.tasks.list_tasks(owner, project.id, todo).total == 2


def test_cached_task_is_not_served_to_a_removed_member(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.join(team, bob)
    task = world.task(owner, world.project(owner, team))
    world.tasks.get_task(bob, task.id)
    world.teams.remove_member(owner, team.id, bob.user_id)
    with pytest.raises(NotFoundError):
        world.tasks.get_task(bob, task.id)


def test_status_change_records_activity_and_sends_signed_webhook(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner), webhook_url="https://hooks.example.com/t")
    task = world.task(owner, project)
    world.tasks.update_task(owner, task.id, _update(status="done"))
    assert world.uow.store.activity[-1].event_type is ActivityType.TASK_STATUS_CHANGED
    assert world.uow.store.activity[-1].details == {"old_status": "todo", "new_status": "done"}
    [delivery] = world.notifier.deliveries
    assert delivery.url == "https://hooks.example.com/t"
    assert delivery.secret == project.webhook_secret
    assert delivery.payload == {
        "event": "task.status_changed",
        "task_id": str(task.id),
        "project_id": str(project.id),
        "old_status": "todo",
        "new_status": "done",
        "actor_id": str(owner.user_id),
        "timestamp": world.clock.now().isoformat(),
    }
    body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
    assert len(sign(delivery.secret, body)) == 64


def test_other_changes_record_task_updated_without_webhook(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner), webhook_url="https://hooks.example.com/t")
    task = world.task(owner, project)
    updated = world.tasks.update_task(
        owner,
        task.id,
        _update(
            title="New", priority="high", due_date="2026-12-01", assignee_id=str(owner.user_id)
        ),
    )
    assert (updated.title, updated.priority, updated.due_date) == ("New", "high", date(2026, 12, 1))
    assert updated.assignee_name == "Olive"
    activity = world.uow.store.activity[-1]
    assert activity.event_type is ActivityType.TASK_UPDATED
    assert activity.details == {"fields": ["assignee_id", "due_date", "priority", "title"]}
    assert world.notifier.deliveries == []
    cleared = world.tasks.update_task(owner, task.id, _update(assignee_id=None, due_date=None))
    assert cleared.assignee_id is None
    assert cleared.due_date is None


def test_noop_update_changes_nothing(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)), "Same")
    before = len(world.uow.store.activity)
    assert world.tasks.update_task(owner, task.id, _update(title="Same")).title == "Same"
    assert len(world.uow.store.activity) == before


def test_required_fields_can_not_be_nulled(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    with pytest.raises(ValidationFailedError):
        world.tasks.update_task(owner, task.id, _update(title=None))


def test_delete_task_removes_attachment_bytes_and_records_activity(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    world.storage.objects["a" * 32] = b"x"
    world.uow.attachments.add(
        Attachment(
            task_id=task.id,
            uploader_id=owner.user_id,
            filename="f",
            content_type="text/plain",
            size_bytes=1,
            storage_key="a" * 32,
        )
    )
    world.tasks.delete_task(owner, task.id)
    assert world.storage.objects == {}
    assert world.uow.store.activity[-1].event_type is ActivityType.TASK_DELETED
    with pytest.raises(NotFoundError):
        world.tasks.get_task(owner, task.id)


def test_delete_survives_storage_errors(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    world.storage.fail_delete = True
    world.uow.attachments.add(
        Attachment(
            task_id=task.id,
            uploader_id=owner.user_id,
            filename="f",
            content_type="text/plain",
            size_bytes=1,
            storage_key="b" * 32,
        )
    )
    world.tasks.delete_task(owner, task.id)
    assert world.uow.tasks.get(task.id) is None


def test_search_only_covers_projects_the_caller_can_see(world: World) -> None:
    olive = world.user("olive")
    mallory = world.user("mallory")
    world.task(olive, world.project(olive, world.team(olive)), "secret plan")
    world.task(mallory, world.project(mallory, world.team(mallory, "Other")), "public plan")
    found = world.tasks.search_tasks(mallory, TaskFilter(text="PLAN"))
    assert [t.title for t in found.items] == ["public plan"]
    assert found.items[0].project_name == "Roadmap"
    admin = world.user("root", role=Role.ADMIN)
    assert world.tasks.search_tasks(admin, TaskFilter(text="plan")).total == 2
    assert world.tasks.search_tasks(world.user("nobody"), TaskFilter()).total == 0


def test_search_filters_sorting_and_pagination(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner))
    world.task(owner, project, "a", priority="low", labels=["x"], due_date="2026-11-01")
    world.task(owner, project, "b", priority="high", assignee_id=str(owner.user_id))
    world.task(owner, project, "c", priority="medium", labels=["x"], due_date="2026-12-01")
    by_priority = world.tasks.search_tasks(
        owner, TaskFilter(sort=SortField.PRIORITY, order=SortOrder.DESC)
    )
    assert [t.title for t in by_priority.items] == ["b", "c", "a"]
    labelled = world.tasks.search_tasks(
        owner, TaskFilter(label="x", sort=SortField.TITLE, order=SortOrder.ASC)
    )
    assert [t.title for t in labelled.items] == ["a", "c"]
    due = world.tasks.search_tasks(owner, TaskFilter(due_before=date(2026, 11, 15)))
    assert [t.title for t in due.items] == ["a"]
    mine = world.tasks.search_tasks(owner, TaskFilter(assignee_id=owner.user_id))
    assert [t.title for t in mine.items] == ["b"]
    by_due = world.tasks.search_tasks(
        owner, TaskFilter(sort=SortField.DUE_DATE, order=SortOrder.ASC)
    )
    assert [t.title for t in by_due.items] == ["a", "c", "b"]
    page = world.tasks.search_tasks(
        owner, TaskFilter(sort=SortField.TITLE, order=SortOrder.ASC, page=PageRequest(2, 2))
    )
    assert ([t.title for t in page.items], page.total, page.page) == (["c"], 3, 2)
