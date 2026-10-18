"""Projects inside a team."""

from uuid import UUID

from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.clock import Clock
from taskboard_api.domain.commands import CreateProjectCommand, UpdateProjectCommand
from taskboard_api.domain.dtos import ActivityDTO, Page, ProjectDetailDTO, ProjectDTO
from taskboard_api.domain.queries import PageRequest, Principal
from taskboard_api.errors import ValidationFailedError
from taskboard_api.models import Project
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.security.tokens import new_token
from taskboard_api.services.access import AccessPolicy, ProjectAccess
from taskboard_api.services.activity import to_page
from taskboard_api.services.export import TaskCsvWriter
from taskboard_api.services.mappers import member_dto, project_dto
from taskboard_api.webhooks.url_guard import UnsafeWebhookUrlError, validate_webhook_url


class ProjectService:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        cache: TaskboardCache,
        clock: Clock,
        webhook_allow_http: bool,
    ) -> None:
        self._uow = uow
        self._cache = cache
        self._clock = clock
        self._allow_http = webhook_allow_http
        self._access = AccessPolicy(uow)

    def list_my_projects(self, principal: Principal) -> list[ProjectDTO]:
        cached = self._cache.get_user_projects(principal.user_id)
        if cached is not None:
            return cached
        team_ids = [team.id for team in self._uow.teams.list_for_user(principal.user_id)]
        projects = [project_dto(p) for p in self._uow.projects.list_for_teams(team_ids)]
        self._cache.set_user_projects(principal.user_id, projects)
        return projects

    def list_team_projects(self, principal: Principal, team_id: UUID) -> list[ProjectDTO]:
        team = self._access.readable_team(principal, team_id)
        return [project_dto(p) for p in self._uow.projects.list_for_team(team.id)]

    def create_project(
        self, principal: Principal, team_id: UUID, command: CreateProjectCommand
    ) -> ProjectDetailDTO:
        team = self._access.managed_team(principal, team_id)
        now = self._clock.now()
        project = Project(team_id=team.id, name=command.name, created_at=now, updated_at=now)
        if command.webhook_url is not None:
            project.webhook_url = self._checked_webhook(command.webhook_url)
            project.webhook_secret = new_token()
        self._uow.projects.add(project)
        self._uow.commit()
        self._invalidate_member_lists(team.id)
        return self._detail(ProjectAccess(project, team, can_manage=True))

    def get_project(self, principal: Principal, project_id: UUID) -> ProjectDetailDTO:
        return self._detail(self._access.readable_project(principal, project_id))

    def update_project(
        self, principal: Principal, project_id: UUID, command: UpdateProjectCommand
    ) -> ProjectDetailDTO:
        access = self._access.managed_project(principal, project_id)
        project = access.project
        self._access.ensure_active(project)
        changed = command.model_fields_set
        if "name" in changed and command.name is not None:
            project.name = command.name
        if "webhook_url" in changed:
            if command.webhook_url is None:
                project.webhook_url = None
                project.webhook_secret = None
            else:
                project.webhook_url = self._checked_webhook(command.webhook_url)
                project.webhook_secret = project.webhook_secret or new_token()
        project.updated_at = self._clock.now()
        self._uow.commit()
        self._invalidate_member_lists(project.team_id)
        return self._detail(access)

    def archive_project(self, principal: Principal, project_id: UUID) -> ProjectDetailDTO:
        access = self._access.managed_project(principal, project_id)
        project = access.project
        if not project.archived:
            now = self._clock.now()
            project.archived = True
            project.archived_at = now
            project.updated_at = now
            self._uow.commit()
            self._invalidate_member_lists(project.team_id)
        return self._detail(access)

    def project_activity(
        self, principal: Principal, project_id: UUID, page: PageRequest
    ) -> Page[ActivityDTO]:
        access = self._access.readable_project(principal, project_id)
        rows, total = self._uow.activity.list_for_project(access.project.id, access.team.id, page)
        return to_page(self._uow, rows, total, page)

    def export_csv(self, principal: Principal, project_id: UUID) -> tuple[str, str]:
        """Return ``(project name, CSV text)``."""
        access = self._access.readable_project(principal, project_id)
        tasks = self._uow.tasks.list_for_project(access.project.id)
        users = self._uow.users.get_many(t.assignee_id for t in tasks if t.assignee_id)
        return access.project.name, TaskCsvWriter().render(tasks, users)

    def _checked_webhook(self, url: str) -> str:
        try:
            return validate_webhook_url(url, allow_http=self._allow_http)
        except UnsafeWebhookUrlError as exc:
            raise ValidationFailedError(str(exc), {"webhook_url": str(exc)}) from exc

    def _invalidate_member_lists(self, team_id: UUID) -> None:
        self._cache.invalidate_user_lists(self._uow.teams.member_ids(team_id), teams=False)

    def _detail(self, access: ProjectAccess) -> ProjectDetailDTO:
        project, team = access.project, access.team
        members = [
            member_dto(member, user, team.owner_id)
            for member, user in self._uow.teams.list_members(team.id)
        ]
        return ProjectDetailDTO(
            **project_dto(project).model_dump(),
            team_name=team.name,
            can_manage=access.can_manage,
            members=members,
            webhook_url=project.webhook_url if access.can_manage else None,
            webhook_secret=project.webhook_secret if access.can_manage else None,
        )
