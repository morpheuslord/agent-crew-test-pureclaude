"""Caller identity and query value objects."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from uuid import UUID

from taskboard_api.domain.enums import Role, SortField, SortOrder, TaskStatus

MAX_PAGE_SIZE = 100
MAX_SEARCH_TEXT = 200


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller, resolved from a session token on every request."""

    user_id: UUID
    email: str
    display_name: str
    role: Role
    session_id: UUID

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN


@dataclass(frozen=True, slots=True)
class PageRequest:
    page: int = 1
    page_size: int = 20

    def __post_init__(self) -> None:
        if self.page < 1:
            msg = "page must be >= 1"
            raise ValueError(msg)
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            msg = f"page_size must be between 1 and {MAX_PAGE_SIZE}"
            raise ValueError(msg)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class TaskFilter:
    """Filters, sort and page for task lists and search.

    ``project_ids=None`` means "every project", which only the service decides (admins).
    """

    project_ids: tuple[UUID, ...] | None = None
    text: str | None = None
    status: TaskStatus | None = None
    assignee_id: UUID | None = None
    label: str | None = None
    due_before: date | None = None
    sort: SortField = SortField.CREATED_AT
    order: SortOrder = SortOrder.DESC
    page: PageRequest = field(default_factory=PageRequest)

    def cache_fingerprint(self) -> str:
        """A stable hash of everything except ``project_ids``, used in cache keys."""
        data = asdict(self)
        data.pop("project_ids")
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
