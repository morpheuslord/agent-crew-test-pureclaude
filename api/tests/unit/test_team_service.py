import pytest

from taskboard_api.domain.commands import AddMemberCommand
from taskboard_api.domain.enums import ActivityType, Role
from taskboard_api.errors import ConflictError, NotFoundError, PermissionDeniedError
from tests.unit.conftest import World


def test_creator_becomes_owner_and_member(world: World) -> None:
    owner = world.user("olive")
    team = world.team(owner)
    detail = world.teams.get_team(owner, team.id)
    assert detail.owner_id == owner.user_id
    assert detail.can_manage
    assert [m.user_id for m in detail.members] == [owner.user_id]
    assert detail.members[0].is_owner


def test_team_list_is_cached_and_invalidated_on_create(world: World) -> None:
    owner = world.user("olive")
    assert world.teams.list_my_teams(owner) == []
    assert world.teams.list_my_teams(owner) == []
    assert world.backend.counters().hits == 1
    world.team(owner)
    assert len(world.teams.list_my_teams(owner)) == 1


def test_non_member_gets_not_found(world: World) -> None:
    team = world.team(world.user("olive"))
    with pytest.raises(NotFoundError):
        world.teams.get_team(world.user("mallory"), team.id)


def test_admin_can_read_any_team(world: World) -> None:
    team = world.team(world.user("olive"))
    detail = world.teams.get_team(world.user("root", role=Role.ADMIN), team.id)
    assert detail.can_manage


def test_owner_adds_member_by_email(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.teams.list_my_teams(bob)
    member = world.teams.add_member(owner, team.id, AddMemberCommand(email="BOB@example.com"))
    assert member.user_id == bob.user_id
    assert [t.id for t in world.teams.list_my_teams(bob)] == [team.id]
    assert world.uow.store.activity[-1].event_type is ActivityType.MEMBER_ADDED


def test_member_can_not_add_members(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    world.user("carol")
    team = world.team(owner)
    world.join(team, bob)
    with pytest.raises(PermissionDeniedError):
        world.teams.add_member(bob, team.id, AddMemberCommand(email="carol@example.com"))


def test_add_member_rejects_unknown_inactive_and_duplicate_users(world: World) -> None:
    owner = world.user("olive")
    world.user("sleepy", active=False)
    team = world.team(owner)
    with pytest.raises(NotFoundError):
        world.teams.add_member(owner, team.id, AddMemberCommand(email="ghost@example.com"))
    with pytest.raises(NotFoundError):
        world.teams.add_member(owner, team.id, AddMemberCommand(email="sleepy@example.com"))
    with pytest.raises(ConflictError):
        world.teams.add_member(owner, team.id, AddMemberCommand(email="olive@example.com"))


def test_remove_member_unassigns_their_tasks_and_records_activity(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.join(team, bob)
    project = world.project(owner, team)
    task = world.task(owner, project, assignee_id=str(bob.user_id))
    assert world.tasks.get_task(owner, task.id).assignee_id == bob.user_id
    world.teams.remove_member(owner, team.id, bob.user_id)
    assert world.tasks.get_task(owner, task.id).assignee_id is None
    assert world.uow.store.activity[-1].event_type is ActivityType.MEMBER_REMOVED
    with pytest.raises(NotFoundError):
        world.teams.get_team(bob, team.id)


def test_owner_can_not_be_removed_and_unknown_member_is_not_found(world: World) -> None:
    owner = world.user("olive")
    team = world.team(owner)
    with pytest.raises(ConflictError):
        world.teams.remove_member(owner, team.id, owner.user_id)
    with pytest.raises(NotFoundError):
        world.teams.remove_member(owner, team.id, world.user("bob").user_id)
