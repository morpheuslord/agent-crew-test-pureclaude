"""Administration of users and the global activity feed."""

import logging
from uuid import UUID

from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.clock import Clock
from taskboard_api.domain.commands import AdminUpdateUserCommand
from taskboard_api.domain.dtos import ActivityDTO, CacheStatsDTO, Page, UserDTO
from taskboard_api.domain.enums import Role
from taskboard_api.domain.queries import PageRequest, Principal
from taskboard_api.errors import NotFoundError, ValidationFailedError
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.services.access import require_admin
from taskboard_api.services.activity import to_page
from taskboard_api.services.mappers import user_dto

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, *, uow: UnitOfWork, cache: TaskboardCache, clock: Clock) -> None:
        self._uow = uow
        self._cache = cache
        self._clock = clock

    def list_users(
        self, principal: Principal, page: PageRequest, query: str | None
    ) -> Page[UserDTO]:
        require_admin(principal)
        users, total = self._uow.users.list(page, query)
        return Page[UserDTO](
            items=[user_dto(user) for user in users],
            page=page.page,
            page_size=page.page_size,
            total=total,
        )

    def update_user(
        self, principal: Principal, user_id: UUID, command: AdminUpdateUserCommand
    ) -> UserDTO:
        require_admin(principal)
        user = self._uow.users.get(user_id)
        if user is None:
            raise NotFoundError("user not found")
        demoting = command.role is not None and command.role is not Role.ADMIN
        deactivating = command.is_active is False
        if user.id == principal.user_id and (demoting or deactivating):
            raise ValidationFailedError("admins can not demote or deactivate their own account")
        if command.role is not None:
            user.role = command.role
        if command.is_active is not None:
            user.is_active = command.is_active
            if not command.is_active:
                self._uow.sessions.delete_for_user(user.id)
        user.updated_at = self._clock.now()
        self._uow.commit()
        self._cache.invalidate_profile(user.id)
        logger.info(
            "user updated by admin",
            extra={
                "admin_id": str(principal.user_id),
                "user_id": str(user.id),
                "role": user.role.value,
                "is_active": user.is_active,
            },
        )
        return user_dto(user)

    def global_activity(self, principal: Principal, page: PageRequest) -> Page[ActivityDTO]:
        require_admin(principal)
        rows, total = self._uow.activity.list_all(page)
        return to_page(self._uow, rows, total, page)

    def cache_stats(self, principal: Principal) -> CacheStatsDTO:
        require_admin(principal)
        return self._cache.stats()
