import re

import pytest

from taskboard_api.domain.commands import (
    ChangePasswordCommand,
    ForgotPasswordCommand,
    LoginCommand,
    RegisterCommand,
    ResetPasswordCommand,
)
from taskboard_api.domain.enums import Role
from taskboard_api.errors import (
    AuthenticationError,
    ConflictError,
    RateLimitedError,
    ValidationFailedError,
)
from taskboard_api.security.tokens import hash_token
from tests.unit.conftest import World

IP = "203.0.113.7"
PASSWORD = "correct horse battery"


def _register(world: World, email: str = "Ada@Example.com") -> None:
    world.auth.register(RegisterCommand(email=email, display_name="Ada", password=PASSWORD), IP)


def _login(world: World, email: str = "ada@example.com", password: str = PASSWORD) -> str:
    return world.auth.login(LoginCommand(email=email, password=password), IP).token


def _reset_token(world: World, email: str) -> str:
    body = world.uow.outbox.list_for(email)[-1].body
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match is not None
    return match.group(1)


def test_register_creates_member_with_hashed_password_and_normalised_email(world: World) -> None:
    _register(world)
    user = world.uow.users.get_by_email("ada@example.com")
    assert user is not None
    assert user.role is Role.MEMBER
    assert user.password_hash != PASSWORD
    assert world.hasher.verify(user.password_hash, PASSWORD)


def test_register_rejects_duplicate_email(world: World) -> None:
    _register(world)
    with pytest.raises(ConflictError):
        _register(world, "ada@example.com")


def test_register_is_rate_limited_per_ip(world: World) -> None:
    for i in range(5):
        _register(world, f"user{i}@example.com")
    with pytest.raises(RateLimitedError) as excinfo:
        _register(world, "one-more@example.com")
    assert excinfo.value.retry_after_seconds > 0


def test_login_returns_token_that_is_stored_only_as_a_hash(world: World) -> None:
    _register(world)
    token = _login(world)
    stored = list(world.uow.store.sessions.values())
    assert len(stored) == 1
    assert stored[0].token_hash == hash_token(token)
    assert token not in stored[0].token_hash


def test_login_with_wrong_password_and_unknown_email_fail_the_same_way(world: World) -> None:
    _register(world)
    with pytest.raises(AuthenticationError) as wrong:
        _login(world, password="wrong password!")
    with pytest.raises(AuthenticationError) as unknown:
        _login(world, email="nobody@example.com")
    assert wrong.value.message == unknown.value.message
    assert world.hasher.dummy_calls == 1


def test_login_of_deactivated_user_fails(world: World) -> None:
    _register(world)
    user = world.uow.users.get_by_email("ada@example.com")
    assert user is not None
    user.is_active = False
    with pytest.raises(AuthenticationError):
        _login(world)


def test_login_is_rate_limited_per_email(world: World) -> None:
    _register(world)
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            _login(world, password="wrong password!")
    with pytest.raises(RateLimitedError):
        _login(world)


def test_login_removes_expired_sessions(world: World) -> None:
    _register(world)
    _login(world)
    world.clock.advance(hours=13)
    _login(world)
    assert len(world.uow.store.sessions) == 1


def test_authenticate_resolves_token_to_principal(world: World) -> None:
    _register(world)
    principal = world.auth.authenticate(_login(world))
    assert principal.email == "ada@example.com"
    assert not principal.is_admin


@pytest.mark.parametrize("token", [None, "", "x" * 201, "not-a-real-token"])
def test_authenticate_rejects_missing_oversized_or_unknown_tokens(
    world: World, token: str | None
) -> None:
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(token)


def test_authenticate_rejects_expired_session(world: World) -> None:
    _register(world)
    token = _login(world)
    world.clock.advance(hours=12)
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(token)


def test_authenticate_rejects_session_of_deactivated_user(world: World) -> None:
    _register(world)
    token = _login(world)
    user = world.uow.users.get_by_email("ada@example.com")
    assert user is not None
    user.is_active = False
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(token)


def test_logout_revokes_the_session(world: World) -> None:
    _register(world)
    token = _login(world)
    world.auth.logout(world.auth.authenticate(token))
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(token)


def test_me_is_served_from_cache_after_first_read(world: World) -> None:
    _register(world)
    principal = world.auth.authenticate(_login(world))
    first = world.auth.me(principal)
    user = world.uow.users.get(principal.user_id)
    assert user is not None
    user.display_name = "Changed directly in the store"
    assert world.auth.me(principal) == first
    assert world.backend.counters().hits == 1


def test_change_password_requires_current_password(world: World) -> None:
    _register(world)
    principal = world.auth.authenticate(_login(world))
    with pytest.raises(ValidationFailedError) as excinfo:
        world.auth.change_password(
            principal,
            ChangePasswordCommand(current_password="wrong", new_password="new password 123"),
        )
    assert "current_password" in excinfo.value.fields


def test_change_password_keeps_current_session_and_revokes_others(world: World) -> None:
    _register(world)
    current = _login(world)
    other = _login(world)
    principal = world.auth.authenticate(current)
    world.auth.change_password(
        principal,
        ChangePasswordCommand(current_password=PASSWORD, new_password="new password 123"),
    )
    world.auth.authenticate(current)
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(other)
    _login(world, password="new password 123")


def test_forgot_password_for_unknown_email_sends_nothing(world: World) -> None:
    world.auth.forgot_password(ForgotPasswordCommand(email="ghost@example.com"), IP)
    assert world.uow.store.outbox == []


def test_forgot_password_writes_reset_link_to_outbox(world: World) -> None:
    _register(world)
    world.auth.forgot_password(ForgotPasswordCommand(email="ada@example.com"), IP)
    message = world.uow.outbox.list_for("ada@example.com")[0]
    assert "https://taskboard.example/reset-password?token=" in message.body
    token = _reset_token(world, "ada@example.com")
    stored = next(iter(world.uow.store.reset_tokens.values()))
    assert stored.token_hash == hash_token(token)


def test_reset_password_sets_password_revokes_sessions_and_is_single_use(world: World) -> None:
    _register(world)
    session_token = _login(world)
    world.auth.forgot_password(ForgotPasswordCommand(email="ada@example.com"), IP)
    token = _reset_token(world, "ada@example.com")
    command = ResetPasswordCommand(token=token, new_password="brand new password")
    world.auth.reset_password(command, IP)
    with pytest.raises(AuthenticationError):
        world.auth.authenticate(session_token)
    _login(world, password="brand new password")
    with pytest.raises(ValidationFailedError):
        world.auth.reset_password(command, IP)


def test_new_reset_request_invalidates_the_previous_link(world: World) -> None:
    _register(world)
    world.auth.forgot_password(ForgotPasswordCommand(email="ada@example.com"), IP)
    first = _reset_token(world, "ada@example.com")
    world.auth.forgot_password(ForgotPasswordCommand(email="ada@example.com"), IP)
    with pytest.raises(ValidationFailedError):
        world.auth.reset_password(
            ResetPasswordCommand(token=first, new_password="brand new password"), IP
        )


def test_reset_link_expires(world: World) -> None:
    _register(world)
    world.auth.forgot_password(ForgotPasswordCommand(email="ada@example.com"), IP)
    token = _reset_token(world, "ada@example.com")
    world.clock.advance(minutes=31)
    with pytest.raises(ValidationFailedError):
        world.auth.reset_password(
            ResetPasswordCommand(token=token, new_password="brand new password"), IP
        )


def test_reset_for_deactivated_user_is_rejected(world: World) -> None:
    _register(world)
    world.auth.forgot_password(ForgotPasswordCommand(email="ada@example.com"), IP)
    token = _reset_token(world, "ada@example.com")
    user = world.uow.users.get_by_email("ada@example.com")
    assert user is not None
    user.is_active = False
    with pytest.raises(ValidationFailedError):
        world.auth.reset_password(
            ResetPasswordCommand(token=token, new_password="brand new password"), IP
        )
