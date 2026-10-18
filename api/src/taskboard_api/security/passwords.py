"""Password hashing."""

import secrets
from typing import Protocol

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password_hash: str, password: str) -> bool: ...
    def verify_dummy(self, password: str) -> None:
        """Spend the same time as a real verification, for callers with no stored hash."""
        ...


class Argon2PasswordHasher:
    """Argon2id with configurable cost."""

    def __init__(self, time_cost: int, memory_cost_kib: int) -> None:
        self._hasher = _Argon2(time_cost=time_cost, memory_cost=memory_cost_kib, parallelism=1)
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        self.verify(self._dummy_hash, password)
