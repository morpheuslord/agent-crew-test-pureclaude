"""Tasks, comments, attachments and the activity log."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from taskboard_api.domain.enums import ActivityType, TaskPriority, TaskStatus
from taskboard_api.models.base import Base, str_enum, utcnow


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_project_id_status", "project_id", "status"),
        Index("ix_tasks_labels", "labels", postgresql_using="gin"),
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"), default=TaskStatus.TODO
    )
    priority: Mapped[TaskPriority] = mapped_column(
        str_enum(TaskPriority, "task_priority"), default=TaskPriority.MEDIUM
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    due_date: Mapped[date | None] = mapped_column(default=None)
    labels: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default_factory=list)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Comment(Base):
    __tablename__ = "comments"

    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Attachment(Base):
    __tablename__ = "attachments"

    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    uploader_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Activity(Base):
    """Append-only event log. ``task_id`` is not a foreign key so history survives deletes."""

    __tablename__ = "activity"
    __table_args__ = (
        Index("ix_activity_project_id_created_at", "project_id", "created_at"),
        Index("ix_activity_team_id_created_at", "team_id", "created_at"),
        Index("ix_activity_created_at", "created_at"),
    )

    event_type: Mapped[ActivityType] = mapped_column(str_enum(ActivityType, "activity_type"))
    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), default=None
    )
    task_id: Mapped[UUID | None] = mapped_column(default=None)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
