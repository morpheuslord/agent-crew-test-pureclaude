"""Users, sessions, password reset tokens and the email outbox."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from taskboard_api.domain.enums import Role
from taskboard_api.models.base import Base, str_enum, utcnow


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255), repr=False)
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    role: Mapped[Role] = mapped_column(str_enum(Role, "user_role"), default=Role.MEMBER)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class UserSession(Base):
    """A login session. Only the SHA-256 of the bearer token is stored."""

    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, repr=False)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, repr=False)
    expires_at: Mapped[datetime]
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class OutboxMessage(Base):
    """An email that would have been sent. There is no real email provider."""

    __tablename__ = "outbox"

    to_address: Mapped[str] = mapped_column(String(254), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
