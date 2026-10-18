"""Tasks: CRUD, per-project lists, search and status-change webhooks."""

import logging
from dataclasses import replace
from typing import Any
from uuid import UUID

from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.clock import Clock
from taskboard_api.domain.commands import CreateTaskCommand, UpdateTaskCommand
from taskboard_api.domain.dtos import Page, TaskDTO, TaskSearchItemDTO
from taskboard_api.domain.enums import ActivityType
from taskboard_api.domain.queries import Principal, TaskFilter
from taskboard_api.errors import ValidationFailedError
from taskboard_api.models import Project, Task
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.services.access import AccessPolicy
from taskboard_api.services.activity import ActivityRecorder
from taskboard_api.services.mappers import task_dto
from taskboard_api.storage.interface import AttachmentStorage
from taskboard_api.webhooks.notifier import WebhookNotifier
from taskboard_api.webhooks.sender import WebhookDelivery

logger = logging.getLogger(__name__)

STATUS_CHANGED_EVENT = "task.status_changed"
_EDITABLE = ("title", "description", "status", "priority", "assignee_id", "due_date", "labels")


class TaskService:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        cache: TaskboardCache,
        clock: Clock,
        notifier: WebhookNotifier,
        storage: AttachmentStorage,
    ) -> None:
        self._uow = uow
        self._cache = cache
        self._clock = clock
        self._notifier = notifier
        self._storage = storage
        self._access = AccessPolicy(uow)
        self._activity = ActivityRecorder(uow, clock)

    def list_tasks(
        self, principal: Principal, project_id: UUID, task_filter: TaskFilter
    ) -> Page[TaskDTO]:
        project = self._access.readable_project(principal, project_id).project
        scoped = replace(task_filter, project_ids=(project.id,))
        fingerprint = scoped.cache_fingerprint()
        cached = self._cache.get_task_page(project.id, fingerprint)
        if cached is not None:
            return cached
        tasks, total = self._uow.tasks.search(scoped)
        page = self._page(tasks, total, scoped)
        self._cache.set_task_page(project.id, fingerprint, page)
        return page

    def create_task(
        self, principal: Principal, project_id: UUID, command: CreateTaskCommand
    ) -> TaskDTO:
        access = self._access.writable_project(principal, project_id)
        self._check_assignee(access.team.id, command.assignee_id)
        now = self._clock.now()
        task = Task(
            project_id=access.project.id,
            title=command.title,
            description=command.description,
            status=command.status,
            priority=command.priority,
            assignee_id=command.assignee_id,
            due_date=command.due_date,
            labels=list(command.labels),
            created_by=principal.user_id,
            created_at=now,
            updated_at=now,
        )
        self._uow.tasks.add(task)
        self._activity.record(
            actor_id=principal.user_id,
            event=ActivityType.TASK_CREATED,
            team_id=access.team.id,
            project_id=access.project.id,
            task_id=task.id,
            details={"title": task.title},
        )
        self._uow.commit()
        self._cache.invalidate_project_tasks(access.project.id)
        return self._dto(task)

    def get_task(self, principal: Principal, task_id: UUID) -> TaskDTO:
        cached = self._cache.get_task(task_id)
        if cached is not None:
            # Authorise against the cached task's project before returning anything.
            self._access.readable_project(principal, cached.project_id)
            return cached
        task = self._access.readable_task(principal, task_id).task
        dto = self._dto(task)
        self._cache.set_task(dto)
        return dto

    def update_task(
        self, principal: Principal, task_id: UUID, command: UpdateTaskCommand
    ) -> TaskDTO:
        access = self._access.writable_task(principal, task_id)
        task = access.task
        requested = {
            name: getattr(command, name) for name in _EDITABLE if name in command.model_fields_set
        }
        for required in ("title", "status", "priority", "labels", "description"):
            if required in requested and requested[required] is None:
                raise ValidationFailedError(f"{required} can not be null", {required: "required"})
        if requested.get("assignee_id") is not None:
            self._check_assignee(access.team.id, requested["assignee_id"])
        changes: dict[str, tuple[Any, Any]] = {}
        for name, value in requested.items():
            old = getattr(task, name)
            if old != value:
                changes[name] = (old, value)
                setattr(task, name, list(value) if name == "labels" else value)
        if not changes:
            return self._dto(task)
        task.updated_at = self._clock.now()
        status_change = changes.pop("status", None)
        if status_change is not None:
            self._activity.record(
                actor_id=principal.user_id,
                event=ActivityType.TASK_STATUS_CHANGED,
                team_id=access.team.id,
                project_id=access.project.id,
                task_id=task.id,
                details={"old_status": str(status_change[0]), "new_status": str(status_change[1])},
            )
        if changes:
            self._activity.record(
                actor_id=principal.user_id,
                event=ActivityType.TASK_UPDATED,
                team_id=access.team.id,
                project_id=access.project.id,
                task_id=task.id,
                details={"fields": sorted(changes)},
            )
        self._uow.commit()
        self._cache.invalidate_tasks([task.id])
        self._cache.invalidate_project_tasks(access.project.id)
        if status_change is not None:
            self._notify_status_change(access.project, task, principal, *status_change)
        return self._dto(task)

    def delete_task(self, principal: Principal, task_id: UUID) -> None:
        access = self._access.writable_task(principal, task_id)
        task = access.task
        storage_keys = [a.storage_key for a in self._uow.attachments.list_for_task(task.id)]
        self._activity.record(
            actor_id=principal.user_id,
            event=ActivityType.TASK_DELETED,
            team_id=access.team.id,
            project_id=access.project.id,
            task_id=task.id,
            details={"title": task.title},
        )
        self._uow.tasks.delete(task)
        self._uow.commit()
        self._cache.invalidate_tasks([task.id])
        self._cache.invalidate_project_tasks(access.project.id)
        for key in storage_keys:
            try:
                self._storage.delete(key)
            except Exception:
                logger.exception("could not delete attachment bytes", extra={"storage_key": key})

    def search_tasks(
        self, principal: Principal, task_filter: TaskFilter
    ) -> Page[TaskSearchItemDTO]:
        if principal.is_admin:
            project_ids: tuple[UUID, ...] | None = None
        else:
            team_ids = [team.id for team in self._uow.teams.list_for_user(principal.user_id)]
            project_ids = tuple(p.id for p in self._uow.projects.list_for_teams(team_ids))
        scoped = replace(task_filter, project_ids=project_ids)
        tasks, total = self._uow.tasks.search(scoped)
        projects = self._uow.projects.get_many(task.project_id for task in tasks)
        users = self._uow.users.get_many(t.assignee_id for t in tasks if t.assignee_id)
        items = [
            TaskSearchItemDTO(
                **task_dto(task, users).model_dump(),
                project_name=projects[task.project_id].name,
            )
            for task in tasks
        ]
        return Page[TaskSearchItemDTO](
            items=items, page=scoped.page.page, page_size=scoped.page.page_size, total=total
        )

    def _check_assignee(self, team_id: UUID, assignee_id: UUID | None) -> None:
        if assignee_id is not None and self._uow.teams.get_member(team_id, assignee_id) is None:
            raise ValidationFailedError(
                "the assignee must be a member of the team", {"assignee_id": "not a team member"}
            )

    def _notify_status_change(
        self, project: Project, task: Task, principal: Principal, old: Any, new: Any
    ) -> None:
        if not project.webhook_url or not project.webhook_secret:
            return
        payload = {
            "event": STATUS_CHANGED_EVENT,
            "task_id": str(task.id),
            "project_id": str(project.id),
            "old_status": str(old),
            "new_status": str(new),
            "actor_id": str(principal.user_id),
            "timestamp": task.updated_at.isoformat(),
        }
        self._notifier.notify(
            WebhookDelivery(
                url=project.webhook_url,
                secret=project.webhook_secret,
                event=STATUS_CHANGED_EVENT,
                payload=payload,
            )
        )

    def _dto(self, task: Task) -> TaskDTO:
        users = self._uow.users.get_many([task.assignee_id] if task.assignee_id else [])
        return task_dto(task, users)

    def _page(self, tasks: list[Task], total: int, task_filter: TaskFilter) -> Page[TaskDTO]:
        users = self._uow.users.get_many(t.assignee_id for t in tasks if t.assignee_id)
        return Page[TaskDTO](
            items=[task_dto(task, users) for task in tasks],
            page=task_filter.page.page,
            page_size=task_filter.page.page_size,
            total=total,
        )
