"""/api/v1/teams: teams, members and a team's projects."""

from uuid import UUID

from fastapi import APIRouter, status

from taskboard_api.api.deps import PrincipalDep
from taskboard_api.composition import ProjectServiceDep, TeamServiceDep
from taskboard_api.domain.commands import AddMemberCommand, CreateProjectCommand, CreateTeamCommand
from taskboard_api.domain.dtos import (
    MemberDTO,
    ProjectDetailDTO,
    ProjectDTO,
    TeamDetailDTO,
    TeamDTO,
)

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("")
def list_teams(principal: PrincipalDep, teams: TeamServiceDep) -> list[TeamDTO]:
    return teams.list_my_teams(principal)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_team(body: CreateTeamCommand, principal: PrincipalDep, teams: TeamServiceDep) -> TeamDTO:
    return teams.create_team(principal, body)


@router.get("/{team_id}")
def get_team(team_id: UUID, principal: PrincipalDep, teams: TeamServiceDep) -> TeamDetailDTO:
    return teams.get_team(principal, team_id)


@router.post("/{team_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    team_id: UUID, body: AddMemberCommand, principal: PrincipalDep, teams: TeamServiceDep
) -> MemberDTO:
    return teams.add_member(principal, team_id, body)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    team_id: UUID, user_id: UUID, principal: PrincipalDep, teams: TeamServiceDep
) -> None:
    teams.remove_member(principal, team_id, user_id)


@router.get("/{team_id}/projects")
def list_team_projects(
    team_id: UUID, principal: PrincipalDep, projects: ProjectServiceDep
) -> list[ProjectDTO]:
    return projects.list_team_projects(principal, team_id)


@router.post("/{team_id}/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    team_id: UUID,
    body: CreateProjectCommand,
    principal: PrincipalDep,
    projects: ProjectServiceDep,
) -> ProjectDetailDTO:
    return projects.create_project(principal, team_id, body)
