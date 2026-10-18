"""SQLAlchemy repositories for users, sessions, reset tokens and the outbox."""

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from taskboard_api.domain.queries import PageRequest
from taskboard_api.models import OutboxMessage, PasswordResetToken, User, UserSession
from taskboard_api.repositories.sql.text import contains_pattern


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> None:
        self._session.add(user)

    def get(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def get_many(self, user_ids: Iterable[UUID]) -> dict[UUID, User]:
        ids = set(user_ids)
        if not ids:
            return {}
        users = self._session.scalars(select(User).where(User.id.in_(ids)))
        return {user.id: user for user in users}

    def list(self, page: PageRequest, query: str | None) -> tuple[list[User], int]:
        stmt = select(User)
        if query:
            pattern = contains_pattern(query)
            stmt = stmt.where(
                or_(
                    User.email.ilike(pattern, escape="\\"),
                    User.display_name.ilike(pattern, escape="\\"),
                )
            )
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self._session.scalars(
            stmt.order_by(User.created_at, User.id).offset(page.offset).limit(page.page_size)
        )
        return list(rows), total


class SqlSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, session: UserSession) -> None:
        self._session.add(session)

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        return self._session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))

    def delete(self, session_id: UUID) -> None:
        self._session.execute(delete(UserSession).where(UserSession.id == session_id))

    def delete_for_user(self, user_id: UUID, *, keep: UUID | None = None) -> None:
        stmt = delete(UserSession).where(UserSession.user_id == user_id)
        if keep is not None:
            stmt = stmt.where(UserSession.id != keep)
        self._session.execute(stmt)

    def delete_expired(self, now: datetime) -> None:
        self._session.execute(delete(UserSession).where(UserSession.expires_at <= now))


class SqlPasswordResetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, token: PasswordResetToken) -> None:
        self._session.add(token)

    def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self._session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )

    def invalidate_for_user(self, user_id: UUID, now: datetime) -> None:
        self._session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )


class SqlOutboxRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, message: OutboxMessage) -> None:
        self._session.add(message)

    def list_for(self, to_address: str) -> list[OutboxMessage]:
        rows = self._session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.to_address == to_address)
            .order_by(OutboxMessage.created_at)
        )
        return list(rows)
