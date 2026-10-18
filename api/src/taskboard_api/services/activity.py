"""Recording and reading the activity log."""

from typing import Any
from uuid import UUID

from taskboard_api.clock import Clock
from taskboard_api.domain.dtos import ActivityDTO, Page
from taskboard_api.domain.enums import ActivityType
from taskboard_api.domain.queries import PageRequest
from taskboard_api.models import Activity
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.services.mappers import activity_dto


class ActivityRecorder:
    """Adds activity rows to the current unit of work; they commit with the change they describe."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def record(
        self,
        *,
        actor_id: UUID,
        event: ActivityType,
        team_id: UUID,
        project_id: UUID | None = None,
        task_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._uow.activity.add(
            Activity(
                actor_id=actor_id,
                event_type=event,
                team_id=team_id,
                project_id=project_id,
                task_id=task_id,
                details=details or {},
                created_at=self._clock.now(),
            )
        )


def to_page(
    uow: UnitOfWork, rows: list[Activity], total: int, page: PageRequest
) -> Page[ActivityDTO]:
    users = uow.users.get_many(row.actor_id for row in rows if row.actor_id is not None)
    return Page[ActivityDTO](
        items=[activity_dto(row, users) for row in rows],
        page=page.page,
        page_size=page.page_size,
        total=total,
    )
