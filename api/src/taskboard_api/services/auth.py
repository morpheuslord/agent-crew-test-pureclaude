"""Registration, login, sessions and password management."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.clock import Clock
from taskboard_api.domain.commands import (
    ChangePasswordCommand,
    ForgotPasswordCommand,
    LoginCommand,
    RegisterCommand,
    ResetPasswordCommand,
)
from taskboard_api.domain.dtos import LoginResultDTO, UserDTO
from taskboard_api.domain.queries import Principal
from taskboard_api.errors import (
    AuthenticationError,
    ConflictError,
    RateLimitedError,
    ValidationFailedError,
)
from taskboard_api.mailer.interface import Mailer
from taskboard_api.models import PasswordResetToken, User, UserSession
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.security.passwords import PasswordHasher
from taskboard_api.security.rate_limit import RateLimiter, limiter_key
from taskboard_api.security.tokens import hash_token, new_token
from taskboard_api.services.mappers import user_dto

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "invalid email or password"
MAX_TOKEN_LENGTH = 200


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    limit: int
    window_seconds: int


@dataclass(frozen=True, slots=True)
class AuthPolicy:
    """Tunables of the authentication service, built from ``Settings``."""

    session_ttl: timedelta
    reset_ttl: timedelta
    public_ui_base: str
    login_per_email: RateLimitRule
    login_per_ip: RateLimitRule
    forgot_per_email: RateLimitRule
    forgot_per_ip: RateLimitRule
    register_per_ip: RateLimitRule
    reset_per_ip: RateLimitRule


class AuthService:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        rate_limiter: RateLimiter,
        mailer: Mailer,
        cache: TaskboardCache,
        clock: Clock,
        policy: AuthPolicy,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._limiter = rate_limiter
        self._mailer = mailer
        self._cache = cache
        self._clock = clock
        self._policy = policy

    def register(self, command: RegisterCommand, client_ip: str) -> UserDTO:
        self._limit("register:ip", client_ip, self._policy.register_per_ip)
        if self._uow.users.get_by_email(command.email) is not None:
            raise ConflictError(
                "an account with this email already exists", {"email": "already registered"}
            )
        now = self._clock.now()
        user = User(
            email=command.email,
            display_name=command.display_name,
            password_hash=self._hasher.hash(command.password),
            created_at=now,
            updated_at=now,
        )
        self._uow.users.add(user)
        self._uow.commit()
        logger.info("user registered", extra={"user_id": str(user.id)})
        return user_dto(user)

    def login(self, command: LoginCommand, client_ip: str) -> LoginResultDTO:
        self._limit("login:ip", client_ip, self._policy.login_per_ip)
        self._limit("login:email", command.email, self._policy.login_per_email)
        user = self._uow.users.get_by_email(command.email)
        if user is None:
            self._hasher.verify_dummy(command.password)
            raise AuthenticationError(INVALID_CREDENTIALS)
        if not self._hasher.verify(user.password_hash, command.password) or not user.is_active:
            raise AuthenticationError(INVALID_CREDENTIALS)
        now = self._clock.now()
        token = new_token()
        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now + self._policy.session_ttl,
            created_at=now,
        )
        self._uow.sessions.delete_expired(now)
        self._uow.sessions.add(session)
        self._uow.commit()
        logger.info("login succeeded", extra={"user_id": str(user.id)})
        return LoginResultDTO(token=token, expires_at=session.expires_at, user=user_dto(user))

    def authenticate(self, token: str | None) -> Principal:
        """Resolve a bearer token to the caller. Never cached, so revocation is immediate."""
        if not token or len(token) > MAX_TOKEN_LENGTH:
            raise AuthenticationError("authentication required")
        session = self._uow.sessions.get_by_token_hash(hash_token(token))
        if session is None or session.expires_at <= self._clock.now():
            raise AuthenticationError("session is invalid or has expired")
        user = self._uow.users.get(session.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("session is invalid or has expired")
        return Principal(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            session_id=session.id,
        )

    def logout(self, principal: Principal) -> None:
        self._uow.sessions.delete(principal.session_id)
        self._uow.commit()

    def me(self, principal: Principal) -> UserDTO:
        cached = self._cache.get_profile(principal.user_id)
        if cached is not None:
            return cached
        user = self._uow.users.get(principal.user_id)
        if user is None:
            raise AuthenticationError("session is invalid or has expired")
        profile = user_dto(user)
        self._cache.set_profile(profile)
        return profile

    def change_password(self, principal: Principal, command: ChangePasswordCommand) -> None:
        self._limit("password:user", str(principal.user_id), self._policy.login_per_email)
        user = self._uow.users.get(principal.user_id)
        if user is None:
            raise AuthenticationError("session is invalid or has expired")
        if not self._hasher.verify(user.password_hash, command.current_password):
            raise ValidationFailedError(
                "current password is incorrect", {"current_password": "incorrect"}
            )
        now = self._clock.now()
        user.password_hash = self._hasher.hash(command.new_password)
        user.updated_at = now
        self._uow.sessions.delete_for_user(user.id, keep=principal.session_id)
        self._uow.reset_tokens.invalidate_for_user(user.id, now)
        self._uow.commit()
        logger.info("password changed", extra={"user_id": str(user.id)})

    def forgot_password(self, command: ForgotPasswordCommand, client_ip: str) -> None:
        """Always succeeds from the caller's point of view, whether or not the account exists."""
        self._limit("forgot:ip", client_ip, self._policy.forgot_per_ip)
        self._limit("forgot:email", command.email, self._policy.forgot_per_email)
        user = self._uow.users.get_by_email(command.email)
        if user is None or not user.is_active:
            return
        now = self._clock.now()
        token = new_token()
        self._uow.reset_tokens.invalidate_for_user(user.id, now)
        self._uow.reset_tokens.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=now + self._policy.reset_ttl,
                created_at=now,
            )
        )
        minutes = int(self._policy.reset_ttl.total_seconds() // 60)
        link = f"{self._policy.public_ui_base}/reset-password?token={token}"
        self._mailer.send(
            user.email,
            "Reset your Taskboard password",
            f"Hello {user.display_name},\n\n"
            f"Use this link within {minutes} minutes to choose a new password:\n{link}\n\n"
            "If you did not ask for this, you can ignore this email.\n",
        )
        self._uow.commit()

    def reset_password(self, command: ResetPasswordCommand, client_ip: str) -> None:
        self._limit("reset:ip", client_ip, self._policy.reset_per_ip)
        invalid = ValidationFailedError(
            "the reset link is invalid or has expired", {"token": "invalid or expired"}
        )
        record = self._uow.reset_tokens.get_by_token_hash(hash_token(command.token))
        now = self._clock.now()
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise invalid
        user = self._uow.users.get(record.user_id)
        if user is None or not user.is_active:
            raise invalid
        user.password_hash = self._hasher.hash(command.new_password)
        user.updated_at = now
        self._uow.reset_tokens.invalidate_for_user(user.id, now)
        self._uow.sessions.delete_for_user(user.id)
        self._uow.commit()
        logger.info("password reset", extra={"user_id": str(user.id)})

    def _limit(self, scope: str, subject: str, rule: RateLimitRule) -> None:
        retry_after = self._limiter.hit(
            limiter_key(scope, subject), rule.limit, rule.window_seconds
        )
        if retry_after is not None:
            logger.warning("rate limit exceeded", extra={"scope": scope})
            raise RateLimitedError("too many attempts, try again later", retry_after)
