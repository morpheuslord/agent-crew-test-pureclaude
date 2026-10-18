"""Enumerations shared by every layer."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActivityType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_DELETED = "task.deleted"
    COMMENT_ADDED = "comment.added"
    ATTACHMENT_ADDED = "attachment.added"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"


class SortField(StrEnum):
    """Task fields a client may sort by. Anything else is rejected before reaching SQL."""

    TITLE = "title"
    DESCRIPTION = "description"
    STATUS = "status"
    PRIORITY = "priority"
    ASSIGNEE_ID = "assignee_id"
    DUE_DATE = "due_date"
    LABELS = "labels"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


STATUS_RANK: dict[TaskStatus, int] = {
    TaskStatus.TODO: 0,
    TaskStatus.IN_PROGRESS: 1,
    TaskStatus.DONE: 2,
}
PRIORITY_RANK: dict[TaskPriority, int] = {
    TaskPriority.LOW: 0,
    TaskPriority.MEDIUM: 1,
    TaskPriority.HIGH: 2,
}
