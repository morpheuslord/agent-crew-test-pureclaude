"""Authorisation rules for teams, projects and tasks, in one place.

Resources the caller can not read raise ``NotFoundError`` (not 403) so that guessing ids does not
reveal whether they exist.
"""

from dataclasses import dataclass
from uuid import UUID

from taskboard_api.domain.queries import Principal
from taskboard_api.errors import ConflictError, NotFoundError, PermissionDeniedError
from taskboard_api.models import Project, Task, Team
from taskboard_api.repositories.interfaces import UnitOfWork


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    project: Project
    team: Team
    can_manage: bool


@dataclass(frozen=True, slots=True)
class TaskAccess:
    task: Task
    project: Project
    team: Team


def require_admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDeniedError("admin role required")


class AccessPolicy:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def is_member(self, principal: Principal, team_id: UUID) -> bool:
        return self._uow.teams.get_member(team_id, principal.user_id) is not None

    def can_manage_team(self, principal: Principal, team: Team) -> bool:
        return principal.is_admin or team.owner_id == principal.user_id

    def readable_team(self, principal: Principal, team_id: UUID) -> Team:
        team = self._uow.teams.get(team_id)
        if team is None or not (principal.is_admin or self.is_member(principal, team_id)):
            raise NotFoundError("team not found")
        return team

    def managed_team(self, principal: Principal, team_id: UUID) -> Team:
        team = self.readable_team(principal, team_id)
        if not self.can_manage_team(principal, team):
            raise PermissionDeniedError("only the team owner or an admin can do this")
        return team

    def readable_project(self, principal: Principal, project_id: UUID) -> ProjectAccess:
        project = self._uow.projects.get(project_id)
        if project is None:
            raise NotFoundError("project not found")
        try:
            team = self.readable_team(principal, project.team_id)
        except NotFoundError:
            raise NotFoundError("project not found") from None
        return ProjectAccess(project, team, self.can_manage_team(principal, team))

    def managed_project(self, principal: Principal, project_id: UUID) -> ProjectAccess:
        access = self.readable_project(principal, project_id)
        if not access.can_manage:
            raise PermissionDeniedError("only the team owner or an admin can do this")
        return access

    def writable_project(self, principal: Principal, project_id: UUID) -> ProjectAccess:
        """Any member may write to an active project's tasks, comments and attachments."""
        access = self.readable_project(principal, project_id)
        self.ensure_active(access.project)
        return access

    def readable_task(self, principal: Principal, task_id: UUID) -> TaskAccess:
        task = self._uow.tasks.get(task_id)
        if task is None:
            raise NotFoundError("task not found")
        try:
            access = self.readable_project(principal, task.project_id)
        except NotFoundError:
            raise NotFoundError("task not found") from None
        return TaskAccess(task, access.project, access.team)

    def writable_task(self, principal: Principal, task_id: UUID) -> TaskAccess:
        access = self.readable_task(principal, task_id)
        self.ensure_active(access.project)
        return access

    @staticmethod
    def ensure_active(project: Project) -> None:
        if project.archived:
            raise ConflictError("the project is archived and read-only")
