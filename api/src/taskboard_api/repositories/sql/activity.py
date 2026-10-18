"""SQLAlchemy repository for the activity log."""

from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from taskboard_api.domain.queries import PageRequest
from taskboard_api.models import Activity


class SqlActivityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, activity: Activity) -> None:
        self._session.add(activity)

    def list_for_project(
        self, project_id: UUID, team_id: UUID, page: PageRequest
    ) -> tuple[list[Activity], int]:
        stmt = select(Activity).where(
            or_(
                Activity.project_id == project_id,
                and_(Activity.team_id == team_id, Activity.project_id.is_(None)),
            )
        )
        return self._page(stmt, page)

    def list_all(self, page: PageRequest) -> tuple[list[Activity], int]:
        return self._page(select(Activity), page)

    def _page(self, stmt: Select[Activity], page: PageRequest) -> tuple[list[Activity], int]:
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self._session.scalars(
            stmt.order_by(Activity.created_at.desc(), Activity.id)
            .offset(page.offset)
            .limit(page.page_size)
        )
        return list(rows), total
