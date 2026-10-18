"""Read models returned by services, cached as JSON and used as API response bodies."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from taskboard_api.domain.enums import ActivityType, Role, TaskPriority, TaskStatus


class _Dto(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class UserDTO(_Dto):
    id: UUID
    email: str
    display_name: str
    role: Role
    is_active: bool
    created_at: datetime


class LoginResultDTO(_Dto):
    token: str
    expires_at: datetime
    user: UserDTO


class MemberDTO(_Dto):
    user_id: UUID
    email: str
    display_name: str
    is_owner: bool
    added_at: datetime


class TeamDTO(_Dto):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime


class TeamDetailDTO(TeamDTO):
    members: list[MemberDTO]
    can_manage: bool


class ProjectDTO(_Dto):
    id: UUID
    team_id: UUID
    name: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectDetailDTO(ProjectDTO):
    team_name: str
    can_manage: bool
    members: list[MemberDTO]
    webhook_url: str | None
    webhook_secret: str | None
    """Only returned to callers who can manage the project; ``None`` for everyone else."""


class TaskDTO(_Dto):
    id: UUID
    project_id: UUID
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    assignee_id: UUID | None
    assignee_name: str | None
    due_date: date | None
    labels: list[str]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class TaskSearchItemDTO(TaskDTO):
    project_name: str


class CommentDTO(_Dto):
    id: UUID
    task_id: UUID
    author_id: UUID
    author_name: str
    body: str
    created_at: datetime
    updated_at: datetime


class AttachmentDTO(_Dto):
    id: UUID
    task_id: UUID
    uploader_id: UUID
    uploader_name: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class ActivityDTO(_Dto):
    id: UUID
    actor_id: UUID | None
    actor_name: str | None
    event_type: ActivityType
    team_id: UUID
    project_id: UUID | None
    task_id: UUID | None
    details: dict[str, Any]
    created_at: datetime


class Page[ItemT](BaseModel):
    """One page of a list endpoint."""

    model_config = ConfigDict(frozen=True)

    items: list[ItemT]
    page: int
    page_size: int
    total: int


class CacheStatsDTO(_Dto):
    backend: str
    hits: int
    misses: int
    errors: int
    available: bool


@dataclass(frozen=True, slots=True)
class AttachmentDownload:
    """An attachment's metadata plus a lazy iterator over its bytes."""

    filename: str
    size_bytes: int
    chunks: Iterator[bytes]
