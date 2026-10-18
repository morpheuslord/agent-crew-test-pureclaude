"""Conversions from ORM entities to read models."""

from collections.abc import Mapping
from uuid import UUID

from taskboard_api.domain.dtos import (
    ActivityDTO,
    AttachmentDTO,
    CommentDTO,
    MemberDTO,
    ProjectDTO,
    TaskDTO,
    TeamDTO,
    UserDTO,
)
from taskboard_api.models import (
    Activity,
    Attachment,
    Comment,
    Project,
    Task,
    Team,
    TeamMember,
    User,
)

UNKNOWN_USER = "(unknown user)"


def user_dto(user: User) -> UserDTO:
    return UserDTO.model_validate(user)


def team_dto(team: Team) -> TeamDTO:
    return TeamDTO.model_validate(team)


def project_dto(project: Project) -> ProjectDTO:
    return ProjectDTO.model_validate(project)


def member_dto(member: TeamMember, user: User, owner_id: UUID) -> MemberDTO:
    return MemberDTO(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_owner=user.id == owner_id,
        added_at=member.added_at,
    )


def _name(users: Mapping[UUID, User], user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    user = users.get(user_id)
    return user.display_name if user else UNKNOWN_USER


def task_dto(task: Task, users: Mapping[UUID, User]) -> TaskDTO:
    return TaskDTO(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assignee_id=task.assignee_id,
        assignee_name=_name(users, task.assignee_id),
        due_date=task.due_date,
        labels=list(task.labels),
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def comment_dto(comment: Comment, users: Mapping[UUID, User]) -> CommentDTO:
    return CommentDTO(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        author_name=_name(users, comment.author_id) or UNKNOWN_USER,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def attachment_dto(attachment: Attachment, users: Mapping[UUID, User]) -> AttachmentDTO:
    return AttachmentDTO(
        id=attachment.id,
        task_id=attachment.task_id,
        uploader_id=attachment.uploader_id,
        uploader_name=_name(users, attachment.uploader_id) or UNKNOWN_USER,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        created_at=attachment.created_at,
    )


def activity_dto(activity: Activity, users: Mapping[UUID, User]) -> ActivityDTO:
    return ActivityDTO(
        id=activity.id,
        actor_id=activity.actor_id,
        actor_name=_name(users, activity.actor_id),
        event_type=activity.event_type,
        team_id=activity.team_id,
        project_id=activity.project_id,
        task_id=activity.task_id,
        details=dict(activity.details),
        created_at=activity.created_at,
    )
