"""Validated inputs to services. The API uses them directly as request bodies.

Every model forbids unknown fields, so a client can not smuggle in attributes such as ``role``.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from taskboard_api.domain.enums import Role, TaskPriority, TaskStatus

MAX_LABELS = 20


def _lower(value: str) -> str:
    return value.lower()


def _unique_labels(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


Email = Annotated[EmailStr, Field(max_length=254), AfterValidator(_lower)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(max_length=20_000)]
CommentBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)
]
# Passwords are never stripped or normalised; the upper bound keeps hashing cost bounded.
NewPassword = Annotated[str, StringConstraints(min_length=10, max_length=128)]
AnyPassword = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Label = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=40,
        pattern=r"^[^\x00-\x1f\x7f,]+$",
    ),
]
Labels = Annotated[list[Label], Field(max_length=MAX_LABELS), AfterValidator(_unique_labels)]
WebhookUrl = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
ResetToken = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class _Command(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegisterCommand(_Command):
    email: Email
    display_name: Name
    password: NewPassword


class LoginCommand(_Command):
    email: Email
    password: AnyPassword


class ChangePasswordCommand(_Command):
    current_password: AnyPassword
    new_password: NewPassword


class ForgotPasswordCommand(_Command):
    email: Email


class ResetPasswordCommand(_Command):
    token: ResetToken
    new_password: NewPassword


class CreateTeamCommand(_Command):
    name: Name


class AddMemberCommand(_Command):
    email: Email


class CreateProjectCommand(_Command):
    name: Name
    webhook_url: WebhookUrl | None = None


class UpdateProjectCommand(_Command):
    """Partial update. Send ``webhook_url: null`` to remove the webhook."""

    name: Name | None = None
    webhook_url: WebhookUrl | None = None


class CreateTaskCommand(_Command):
    title: Title
    description: Description = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: UUID | None = None
    due_date: date | None = None
    labels: Labels = Field(default_factory=list)


class UpdateTaskCommand(_Command):
    """Partial update; only fields present in the request are changed (see ``model_fields_set``).

    ``assignee_id`` and ``due_date`` may be sent as ``null`` to clear them.
    """

    title: Title | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None
    labels: Labels | None = None


class CommentCommand(_Command):
    body: CommentBody


class AdminUpdateUserCommand(_Command):
    role: Role | None = None
    is_active: bool | None = None
