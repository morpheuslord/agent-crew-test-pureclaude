"""SQLAlchemy Unit of Work: one session and one transaction per request."""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from taskboard_api.repositories.interfaces import (
    ActivityRepository,
    AttachmentRepository,
    CommentRepository,
    OutboxRepository,
    PasswordResetRepository,
    ProjectRepository,
    SessionRepository,
    TaskRepository,
    TeamRepository,
    UserRepository,
)
from taskboard_api.repositories.sql.accounts import (
    SqlOutboxRepository,
    SqlPasswordResetRepository,
    SqlSessionRepository,
    SqlUserRepository,
)
from taskboard_api.repositories.sql.activity import SqlActivityRepository
from taskboard_api.repositories.sql.tasks import (
    SqlAttachmentRepository,
    SqlCommentRepository,
    SqlTaskRepository,
)
from taskboard_api.repositories.sql.teams import SqlProjectRepository, SqlTeamRepository


class SqlUnitOfWork:
    """Implements ``UnitOfWork`` on top of one SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.users: UserRepository = SqlUserRepository(session)
        self.sessions: SessionRepository = SqlSessionRepository(session)
        self.reset_tokens: PasswordResetRepository = SqlPasswordResetRepository(session)
        self.outbox: OutboxRepository = SqlOutboxRepository(session)
        self.teams: TeamRepository = SqlTeamRepository(session)
        self.projects: ProjectRepository = SqlProjectRepository(session)
        self.tasks: TaskRepository = SqlTaskRepository(session)
        self.comments: CommentRepository = SqlCommentRepository(session)
        self.attachments: AttachmentRepository = SqlAttachmentRepository(session)
        self.activity: ActivityRepository = SqlActivityRepository(session)

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        self.close()
