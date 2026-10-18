"""SQLAlchemy repositories for teams, memberships and projects."""

from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from taskboard_api.models import Project, Team, TeamMember, User


class SqlTeamRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, team: Team) -> None:
        self._session.add(team)

    def get(self, team_id: UUID) -> Team | None:
        return self._session.get(Team, team_id)

    def list_for_user(self, user_id: UUID) -> list[Team]:
        rows = self._session.scalars(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user_id)
            .order_by(Team.name, Team.id)
        )
        return list(rows)

    def add_member(self, member: TeamMember) -> None:
        self._session.add(member)

    def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        self._session.execute(
            delete(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )

    def get_member(self, team_id: UUID, user_id: UUID) -> TeamMember | None:
        return self._session.get(TeamMember, (team_id, user_id))

    def list_members(self, team_id: UUID) -> list[tuple[TeamMember, User]]:
        rows = self._session.execute(
            select(TeamMember, User)
            .join(User, User.id == TeamMember.user_id)
            .where(TeamMember.team_id == team_id)
            .order_by(User.display_name, User.id)
        )
        return [(member, user) for member, user in rows]

    def member_ids(self, team_id: UUID) -> list[UUID]:
        rows = self._session.scalars(
            select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        )
        return list(rows)


class SqlProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, project: Project) -> None:
        self._session.add(project)

    def get(self, project_id: UUID) -> Project | None:
        return self._session.get(Project, project_id)

    def get_many(self, project_ids: Iterable[UUID]) -> dict[UUID, Project]:
        ids = set(project_ids)
        if not ids:
            return {}
        rows = self._session.scalars(select(Project).where(Project.id.in_(ids)))
        return {project.id: project for project in rows}

    def list_for_team(self, team_id: UUID) -> list[Project]:
        return self.list_for_teams([team_id])

    def list_for_teams(self, team_ids: Sequence[UUID]) -> list[Project]:
        if not team_ids:
            return []
        rows = self._session.scalars(
            select(Project)
            .where(Project.team_id.in_(team_ids))
            .order_by(Project.archived, Project.name, Project.id)
        )
        return list(rows)
