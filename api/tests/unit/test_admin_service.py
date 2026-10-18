import pytest

from taskboard_api.domain.commands import AdminUpdateUserCommand, LoginCommand, RegisterCommand
from taskboard_api.domain.enums import Role
from taskboard_api.domain.queries import PageRequest
from taskboard_api.errors import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from taskboard_api.services.bootstrap import AdminBootstrapService, BootstrapOutcome
from tests.unit.conftest import World


def test_only_admins_use_admin_functions(world: World) -> None:
    member = world.user("bob")
    with pytest.raises(PermissionDeniedError):
        world.admin.list_users(member, PageRequest(), None)
    with pytest.raises(PermissionDeniedError):
        world.admin.global_activity(member, PageRequest())
    with pytest.raises(PermissionDeniedError):
        world.admin.cache_stats(member)
    with pytest.raises(PermissionDeniedError):
        world.admin.update_user(member, member.user_id, AdminUpdateUserCommand(role=Role.ADMIN))


def test_list_users_filters_and_pages(world: World) -> None:
    admin = world.user("root", role=Role.ADMIN)
    world.user("alice")
    world.user("bob")
    page = world.admin.list_users(admin, PageRequest(1, 2), None)
    assert (len(page.items), page.total) == (2, 3)
    assert [u.email for u in world.admin.list_users(admin, PageRequest(), "ALI").items] == [
        "alice@example.com"
    ]


def test_deactivation_revokes_sessions_and_blocks_login(world: World) -> None:
    admin = world.user("root", role=Role.ADMIN)
    world.auth.register(
        RegisterCommand(email="bob@example.com", display_name="Bob", password="bob password 1"),
        "198.51.100.1",
    )
    login = LoginCommand(email="bob@example.com", password="bob password 1")
    token = world.auth.login(login, "198.51.100.1").token
    bob = world.auth.authenticate(token)
    world.auth.me(bob)
    updated = world.admin.update_user(admin, bob.user_id, AdminUpdateUserCommand(is_active=False))
    assert not updated.is_active
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(token)
    with pytest.raises(AuthenticationError):
        world.auth.login(login, "198.51.100.1")
    world.admin.update_user(admin, bob.user_id, AdminUpdateUserCommand(is_active=True))
    world.auth.login(login, "198.51.100.1")


def test_role_change_and_self_protection(world: World) -> None:
    admin = world.user("root", role=Role.ADMIN)
    bob = world.user("bob")
    assert world.admin.update_user(admin, bob.user_id, AdminUpdateUserCommand(role=Role.ADMIN)).role
    with pytest.raises(ValidationFailedError):
        world.admin.update_user(admin, admin.user_id, AdminUpdateUserCommand(role=Role.MEMBER))
    with pytest.raises(ValidationFailedError):
        world.admin.update_user(admin, admin.user_id, AdminUpdateUserCommand(is_active=False))
    with pytest.raises(NotFoundError):
        world.admin.update_user(admin, bob.session_id, AdminUpdateUserCommand(role=Role.MEMBER))


def test_global_activity_and_cache_stats(world: World) -> None:
    admin = world.user("root", role=Role.ADMIN)
    owner = world.user("olive")
    world.task(owner, world.project(owner, world.team(owner)))
    assert world.admin.global_activity(admin, PageRequest()).total == 1
    stats = world.admin.cache_stats(admin)
    assert stats.backend == "memory"
    assert stats.available


def test_bootstrap_creates_then_promotes_then_leaves_admin_alone(world: World) -> None:
    service = AdminBootstrapService(uow=world.uow, hasher=world.hasher, clock=world.clock)
    command = RegisterCommand(
        email="admin@example.com", display_name="Admin", password="admin password 1"
    )
    assert service.ensure_admin(command) is BootstrapOutcome.CREATED
    assert service.ensure_admin(command) is BootstrapOutcome.UNCHANGED
    user = world.uow.users.get_by_email("admin@example.com")
    assert user is not None
    user.role = Role.MEMBER
    user.is_active = False
    assert service.ensure_admin(command) is BootstrapOutcome.PROMOTED
    assert user.role is Role.ADMIN
    assert user.is_active
