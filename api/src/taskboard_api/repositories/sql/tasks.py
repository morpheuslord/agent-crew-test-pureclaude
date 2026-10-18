"""SQLAlchemy repositories for tasks, comments and attachments."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, case, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from taskboard_api.domain.enums import PRIORITY_RANK, STATUS_RANK, SortField, SortOrder
from taskboard_api.domain.queries import TaskFilter
from taskboard_api.models import Attachment, Comment, Task
from taskboard_api.repositories.sql.text import contains_pattern

# The only way a client-supplied sort field reaches SQL: as a key into this allow-list.
_SORT_COLUMNS: dict[SortField, ColumnElement[Any] | InstrumentedAttribute[Any]] = {
    SortField.TITLE: Task.title,
    SortField.DESCRIPTION: Task.description,
    SortField.STATUS: case(dict(STATUS_RANK.items()), value=Task.status),
    SortField.PRIORITY: case(dict(PRIORITY_RANK.items()), value=Task.priority),
    SortField.ASSIGNEE_ID: Task.assignee_id,
    SortField.DUE_DATE: Task.due_date,
    SortField.LABELS: Task.labels,
    SortField.CREATED_AT: Task.created_at,
    SortField.UPDATED_AT: Task.updated_at,
}


def _filtered(task_filter: TaskFilter) -> Select[Task]:
    stmt = select(Task)
    if task_filter.project_ids is not None:
        stmt = stmt.where(Task.project_id.in_(task_filter.project_ids))
    if task_filter.text:
        pattern = contains_pattern(task_filter.text)
        stmt = stmt.where(
            or_(
                Task.title.ilike(pattern, escape="\\"),
                Task.description.ilike(pattern, escape="\\"),
            )
        )
    if task_filter.status is not None:
        stmt = stmt.where(Task.status == task_filter.status)
    if task_filter.assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == task_filter.assignee_id)
    if task_filter.label:
        stmt = stmt.where(Task.labels.contains([task_filter.label]))
    if task_filter.due_before is not None:
        stmt = stmt.where(Task.due_date < task_filter.due_before)
    return stmt


class SqlTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: Task) -> None:
        self._session.add(task)

    def get(self, task_id: UUID) -> Task | None:
        return self._session.get(Task, task_id)

    def delete(self, task: Task) -> None:
        self._session.delete(task)

    def search(self, task_filter: TaskFilter) -> tuple[list[Task], int]:
        if task_filter.project_ids == ():
            return [], 0
        stmt = _filtered(task_filter)
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        column = _SORT_COLUMNS[task_filter.sort]
        ordering = column.asc() if task_filter.order is SortOrder.ASC else column.desc()
        page = task_filter.page
        rows = self._session.scalars(
            stmt.order_by(ordering.nulls_last(), Task.id).offset(page.offset).limit(page.page_size)
        )
        return list(rows), total

    def list_for_project(self, project_id: UUID) -> list[Task]:
        rows = self._session.scalars(
            select(Task).where(Task.project_id == project_id).order_by(Task.created_at, Task.id)
        )
        return list(rows)

    def unassign(self, project_ids: Sequence[UUID], user_id: UUID) -> list[Task]:
        if not project_ids:
            return []
        tasks = list(
            self._session.scalars(
                select(Task).where(Task.project_id.in_(project_ids), Task.assignee_id == user_id)
            )
        )
        for task in tasks:
            task.assignee_id = None
        return tasks


class SqlCommentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, comment: Comment) -> None:
        self._session.add(comment)

    def get(self, comment_id: UUID) -> Comment | None:
        return self._session.get(Comment, comment_id)

    def delete(self, comment: Comment) -> None:
        self._session.delete(comment)

    def list_for_task(self, task_id: UUID) -> list[Comment]:
        rows = self._session.scalars(
            select(Comment)
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at, Comment.id)
        )
        return list(rows)


class SqlAttachmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, attachment: Attachment) -> None:
        self._session.add(attachment)

    def get(self, attachment_id: UUID) -> Attachment | None:
        return self._session.get(Attachment, attachment_id)

    def list_for_task(self, task_id: UUID) -> list[Attachment]:
        rows = self._session.scalars(
            select(Attachment)
            .where(Attachment.task_id == task_id)
            .order_by(Attachment.created_at, Attachment.id)
        )
        return list(rows)
