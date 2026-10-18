"""Teams, memberships and projects."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from taskboard_api.models.base import Base, utcnow


class Team(Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Project(Base):
    __tablename__ = "projects"

    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    archived: Mapped[bool] = mapped_column(default=False)
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
    webhook_url: Mapped[str | None] = mapped_column(Text, default=None)
    webhook_secret: Mapped[str | None] = mapped_column(String(64), default=None, repr=False)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
