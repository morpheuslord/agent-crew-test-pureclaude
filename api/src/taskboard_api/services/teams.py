"""Teams and team membership."""

from uuid import UUID

from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.clock import Clock
from taskboard_api.domain.commands import AddMemberCommand, CreateTeamCommand
from taskboard_api.domain.dtos import MemberDTO, TeamDetailDTO, TeamDTO
from taskboard_api.domain.enums import ActivityType
from taskboard_api.domain.queries import Principal
from taskboard_api.errors import ConflictError, NotFoundError
from taskboard_api.models import Team, TeamMember
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.services.access import AccessPolicy
from taskboard_api.services.activity import ActivityRecorder
from taskboard_api.services.mappers import member_dto, team_dto


class TeamService:
    def __init__(self, *, uow: UnitOfWork, cache: TaskboardCache, clock: Clock) -> None:
        self._uow = uow
        self._cache = cache
        self._clock = clock
        self._access = AccessPolicy(uow)
        self._activity = ActivityRecorder(uow, clock)

    def list_my_teams(self, principal: Principal) -> list[TeamDTO]:
        cached = self._cache.get_user_teams(principal.user_id)
        if cached is not None:
            return cached
        teams = [team_dto(team) for team in self._uow.teams.list_for_user(principal.user_id)]
        self._cache.set_user_teams(principal.user_id, teams)
        return teams

    def create_team(self, principal: Principal, command: CreateTeamCommand) -> TeamDTO:
        now = self._clock.now()
        team = Team(name=command.name, owner_id=principal.user_id, created_at=now)
        self._uow.teams.add(team)
        self._uow.flush()
        self._uow.teams.add_member(
            TeamMember(team_id=team.id, user_id=principal.user_id, added_at=now)
        )
        self._uow.commit()
        self._cache.invalidate_user_lists([principal.user_id])
        return team_dto(team)

    def get_team(self, principal: Principal, team_id: UUID) -> TeamDetailDTO:
        team = self._access.readable_team(principal, team_id)
        members = [
            member_dto(member, user, team.owner_id)
            for member, user in self._uow.teams.list_members(team.id)
        ]
        return TeamDetailDTO(
            **team_dto(team).model_dump(),
            members=members,
            can_manage=self._access.can_manage_team(principal, team),
        )

    def add_member(
        self, principal: Principal, team_id: UUID, command: AddMemberCommand
    ) -> MemberDTO:
        team = self._access.managed_team(principal, team_id)
        user = self._uow.users.get_by_email(command.email)
        if user is None or not user.is_active:
            raise NotFoundError("no active user has that email address", {"email": "not found"})
        if self._uow.teams.get_member(team.id, user.id) is not None:
            raise ConflictError("that user is already a member", {"email": "already a member"})
        member = TeamMember(team_id=team.id, user_id=user.id, added_at=self._clock.now())
        self._uow.teams.add_member(member)
        self._activity.record(
            actor_id=principal.user_id,
            event=ActivityType.MEMBER_ADDED,
            team_id=team.id,
            details={"user_id": str(user.id), "display_name": user.display_name},
        )
        self._uow.commit()
        self._cache.invalidate_user_lists([user.id])
        return member_dto(member, user, team.owner_id)

    def remove_member(self, principal: Principal, team_id: UUID, user_id: UUID) -> None:
        team = self._access.managed_team(principal, team_id)
        if user_id == team.owner_id:
            raise ConflictError("the team owner can not be removed")
        if self._uow.teams.get_member(team.id, user_id) is None:
            raise NotFoundError("member not found")
        user = self._uow.users.get(user_id)
        self._uow.teams.remove_member(team.id, user_id)
        project_ids = [project.id for project in self._uow.projects.list_for_team(team.id)]
        unassigned = self._uow.tasks.unassign(project_ids, user_id)
        self._activity.record(
            actor_id=principal.user_id,
            event=ActivityType.MEMBER_REMOVED,
            team_id=team.id,
            details={
                "user_id": str(user_id),
                "display_name": user.display_name if user else None,
                "unassigned_tasks": len(unassigned),
            },
        )
        self._uow.commit()
        self._cache.invalidate_user_lists([user_id])
        for project_id in {task.project_id for task in unassigned}:
            self._cache.invalidate_project_tasks(project_id)
        self._cache.invalidate_tasks(task.id for task in unassigned)
