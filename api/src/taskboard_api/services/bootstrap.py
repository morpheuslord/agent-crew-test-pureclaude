"""Creating the first administrator."""

from enum import StrEnum

from taskboard_api.clock import Clock
from taskboard_api.domain.commands import RegisterCommand
from taskboard_api.domain.enums import Role
from taskboard_api.models import User
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.security.passwords import PasswordHasher


class BootstrapOutcome(StrEnum):
    CREATED = "created"
    PROMOTED = "promoted"
    UNCHANGED = "unchanged"


class AdminBootstrapService:
    """Idempotent: creates the admin, or promotes and reactivates an existing account.

    An existing account's password is never changed, so re-running the command is harmless.
    """

    def __init__(self, *, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    def ensure_admin(self, command: RegisterCommand) -> BootstrapOutcome:
        now = self._clock.now()
        user = self._uow.users.get_by_email(command.email)
        if user is None:
            self._uow.users.add(
                User(
                    email=command.email,
                    display_name=command.display_name,
                    password_hash=self._hasher.hash(command.password),
                    role=Role.ADMIN,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._uow.commit()
            return BootstrapOutcome.CREATED
        if user.role is Role.ADMIN and user.is_active:
            return BootstrapOutcome.UNCHANGED
        user.role = Role.ADMIN
        user.is_active = True
        user.updated_at = now
        self._uow.commit()
        return BootstrapOutcome.PROMOTED
