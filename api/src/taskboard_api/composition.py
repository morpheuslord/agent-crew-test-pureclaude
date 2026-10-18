"""Composition root: the only module that chooses concrete implementations.

``Container`` holds process-wide singletons. The ``get_*`` functions are FastAPI dependencies that
build request-scoped services around one unit of work.
"""

import logging
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Annotated, cast

import boto3
from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from taskboard_api.cache.interface import Cache
from taskboard_api.cache.memory import NullCache
from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.clock import Clock, SystemClock
from taskboard_api.config import Settings
from taskboard_api.mailer.outbox import OutboxMailer
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.repositories.sql.uow import SqlUnitOfWork
from taskboard_api.security.passwords import Argon2PasswordHasher, PasswordHasher
from taskboard_api.security.rate_limit import InMemoryRateLimiter, RateLimiter
from taskboard_api.services.admin import AdminService
from taskboard_api.services.attachments import AttachmentService
from taskboard_api.services.auth import AuthPolicy, AuthService, RateLimitRule
from taskboard_api.services.comments import CommentService
from taskboard_api.services.projects import ProjectService
from taskboard_api.services.tasks import TaskService
from taskboard_api.services.teams import TeamService
from taskboard_api.storage.interface import AttachmentStorage
from taskboard_api.storage.local import LocalFileStorage
from taskboard_api.storage.s3 import S3Storage
from taskboard_api.webhooks.notifier import ThreadPoolWebhookNotifier, WebhookNotifier
from taskboard_api.webhooks.sender import HttpWebhookSender

logger = logging.getLogger(__name__)


class Container:
    """Process-wide dependencies. Tests pass fakes for any of the optional arguments."""

    def __init__(
        self,
        settings: Settings,
        *,
        engine: Engine | None = None,
        cache: Cache | None = None,
        storage: AttachmentStorage | None = None,
        notifier: WebhookNotifier | None = None,
        hasher: PasswordHasher | None = None,
        rate_limiter: RateLimiter | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.settings = settings
        self.engine = engine or create_engine(
            settings.database_url.get_secret_value(),
            pool_size=settings.database_pool_size,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self.cache_backend = cache or NullCache()
        self.cache = TaskboardCache(self.cache_backend, settings.cache_ttl_seconds)
        self.storage = storage or self._build_storage(settings)
        self.notifier = notifier or self._build_notifier(settings)
        self.hasher = hasher or Argon2PasswordHasher(
            settings.argon2_time_cost, settings.argon2_memory_cost_kib
        )
        self.rate_limiter = rate_limiter or InMemoryRateLimiter()
        self.clock = clock or SystemClock()
        self.auth_policy = _auth_policy(settings)

    def unit_of_work(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self.session_factory())

    def database_ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("readiness: database unavailable")
            return False
        return True

    def close(self) -> None:
        self.notifier.close()
        self.engine.dispose()

    @staticmethod
    def _build_storage(settings: Settings) -> AttachmentStorage:
        if settings.storage_backend == "s3":
            client = boto3.client("s3", region_name=settings.aws_region)
            return S3Storage(
                client, cast(str, settings.s3_bucket), settings.s3_prefix, settings.s3_kms_key_id
            )
        return LocalFileStorage(Path(settings.storage_local_path))

    @staticmethod
    def _build_notifier(settings: Settings) -> WebhookNotifier:
        sender = HttpWebhookSender(
            timeout_seconds=settings.webhook_timeout_seconds,
            allow_http=settings.webhook_allow_http,
            allow_private=settings.webhook_allow_private_targets,
        )
        return ThreadPoolWebhookNotifier(
            sender,
            workers=settings.webhook_workers,
            max_attempts=settings.webhook_max_attempts,
            backoff_seconds=settings.webhook_backoff_seconds,
        )


def _auth_policy(settings: Settings) -> AuthPolicy:
    slow = settings.slow_rate_window_seconds
    return AuthPolicy(
        session_ttl=timedelta(hours=settings.session_ttl_hours),
        reset_ttl=timedelta(minutes=settings.password_reset_ttl_minutes),
        public_ui_base=settings.public_ui_base,
        login_per_email=RateLimitRule(
            settings.login_rate_limit_per_email, settings.login_rate_window_seconds
        ),
        login_per_ip=RateLimitRule(
            settings.login_rate_limit_per_ip, settings.login_rate_window_seconds
        ),
        forgot_per_email=RateLimitRule(settings.forgot_rate_limit_per_email, slow),
        forgot_per_ip=RateLimitRule(settings.forgot_rate_limit_per_ip, slow),
        register_per_ip=RateLimitRule(settings.register_rate_limit_per_ip, slow),
        reset_per_ip=RateLimitRule(settings.reset_rate_limit_per_ip, slow),
    )


# FastAPI dependency providers -------------------------------------------------------------------


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


ContainerDep = Annotated[Container, Depends(get_container)]


def get_uow(container: ContainerDep) -> Iterator[UnitOfWork]:
    with container.unit_of_work() as uow:
        yield uow


UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_auth_service(uow: UowDep, container: ContainerDep) -> AuthService:
    return AuthService(
        uow=uow,
        hasher=container.hasher,
        rate_limiter=container.rate_limiter,
        mailer=OutboxMailer(uow.outbox, log_body=container.settings.mailer_log_body),
        cache=container.cache,
        clock=container.clock,
        policy=container.auth_policy,
    )


def get_admin_service(uow: UowDep, container: ContainerDep) -> AdminService:
    return AdminService(uow=uow, cache=container.cache, clock=container.clock)


def get_team_service(uow: UowDep, container: ContainerDep) -> TeamService:
    return TeamService(uow=uow, cache=container.cache, clock=container.clock)


def get_project_service(uow: UowDep, container: ContainerDep) -> ProjectService:
    return ProjectService(
        uow=uow,
        cache=container.cache,
        clock=container.clock,
        webhook_allow_http=container.settings.webhook_allow_http,
    )


def get_task_service(uow: UowDep, container: ContainerDep) -> TaskService:
    return TaskService(
        uow=uow,
        cache=container.cache,
        clock=container.clock,
        notifier=container.notifier,
        storage=container.storage,
    )


def get_comment_service(uow: UowDep, container: ContainerDep) -> CommentService:
    return CommentService(uow=uow, clock=container.clock)


def get_attachment_service(uow: UowDep, container: ContainerDep) -> AttachmentService:
    return AttachmentService(
        uow=uow,
        storage=container.storage,
        clock=container.clock,
        max_upload_bytes=container.settings.max_upload_bytes,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]
AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]
