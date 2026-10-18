"""Typed cache-aside facade: owns key naming, serialisation and invalidation rules."""

import logging
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from taskboard_api.cache.interface import Cache
from taskboard_api.domain.dtos import CacheStatsDTO, Page, ProjectDTO, TaskDTO, TeamDTO, UserDTO

logger = logging.getLogger(__name__)

_PREFIX = "tb"
_TEAMS = TypeAdapter(list[TeamDTO])
_PROJECTS = TypeAdapter(list[ProjectDTO])
_TASK_PAGE = TypeAdapter(Page[TaskDTO])
_TASK = TypeAdapter(TaskDTO)
_USER = TypeAdapter(UserDTO)


def profile_key(user_id: UUID) -> str:
    return f"{_PREFIX}:user:{user_id}:profile"


def user_teams_key(user_id: UUID) -> str:
    return f"{_PREFIX}:user:{user_id}:teams"


def user_projects_key(user_id: UUID) -> str:
    return f"{_PREFIX}:user:{user_id}:projects"


def task_key(task_id: UUID) -> str:
    return f"{_PREFIX}:task:{task_id}"


def task_page_key(project_id: UUID, fingerprint: str) -> str:
    return f"{_PREFIX}:project:{project_id}:tasks:{fingerprint}"


def task_index_key(project_id: UUID) -> str:
    return f"{_PREFIX}:project:{project_id}:tasks:index"


class TaskboardCache:
    """What the services cache, and which keys each write must invalidate.

    Callers must perform authorisation before reading from the cache: keys are per object or per
    user and never mix data that different callers are allowed to see.
    """

    def __init__(self, cache: Cache, ttl_seconds: int) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    # Reads -----------------------------------------------------------------------------------

    def get_profile(self, user_id: UUID) -> UserDTO | None:
        return self._read(profile_key(user_id), _USER)

    def set_profile(self, user: UserDTO) -> None:
        self._write(profile_key(user.id), _USER, user)

    def get_user_teams(self, user_id: UUID) -> list[TeamDTO] | None:
        return self._read(user_teams_key(user_id), _TEAMS)

    def set_user_teams(self, user_id: UUID, teams: list[TeamDTO]) -> None:
        self._write(user_teams_key(user_id), _TEAMS, teams)

    def get_user_projects(self, user_id: UUID) -> list[ProjectDTO] | None:
        return self._read(user_projects_key(user_id), _PROJECTS)

    def set_user_projects(self, user_id: UUID, projects: list[ProjectDTO]) -> None:
        self._write(user_projects_key(user_id), _PROJECTS, projects)

    def get_task(self, task_id: UUID) -> TaskDTO | None:
        return self._read(task_key(task_id), _TASK)

    def set_task(self, task: TaskDTO) -> None:
        self._write(task_key(task.id), _TASK, task)

    def get_task_page(self, project_id: UUID, fingerprint: str) -> Page[TaskDTO] | None:
        return self._read(task_page_key(project_id, fingerprint), _TASK_PAGE)

    def set_task_page(self, project_id: UUID, fingerprint: str, page: Page[TaskDTO]) -> None:
        key = task_page_key(project_id, fingerprint)
        self._write(key, _TASK_PAGE, page)
        self._cache.add_to_index(task_index_key(project_id), key, self._ttl)

    # Invalidation ----------------------------------------------------------------------------

    def invalidate_profile(self, user_id: UUID) -> None:
        self._cache.delete(profile_key(user_id))

    def invalidate_user_lists(
        self, user_ids: Iterable[UUID], *, teams: bool = True, projects: bool = True
    ) -> None:
        keys: list[str] = []
        for user_id in user_ids:
            if teams:
                keys.append(user_teams_key(user_id))
            if projects:
                keys.append(user_projects_key(user_id))
        self._cache.delete(*keys)

    def invalidate_project_tasks(self, project_id: UUID) -> None:
        self._cache.invalidate_index(task_index_key(project_id))

    def invalidate_tasks(self, task_ids: Iterable[UUID]) -> None:
        self._cache.delete(*(task_key(task_id) for task_id in task_ids))

    # Stats -----------------------------------------------------------------------------------

    def stats(self) -> CacheStatsDTO:
        counters = self._cache.counters()
        return CacheStatsDTO(
            backend=self._cache.backend_name,
            hits=counters.hits,
            misses=counters.misses,
            errors=counters.errors,
            available=self._cache.available(),
        )

    # Helpers ---------------------------------------------------------------------------------

    def _read[T](self, key: str, adapter: TypeAdapter[T]) -> T | None:
        raw = self._cache.get(key)
        if raw is None:
            return None
        try:
            return adapter.validate_json(raw)
        except ValidationError:
            # A stale entry from an older schema: drop it and fall back to the database.
            logger.warning("cache: discarding undecodable entry", extra={"cache_key": key})
            self._cache.delete(key)
            return None

    def _write(self, key: str, adapter: TypeAdapter[Any], value: object) -> None:
        self._cache.set(key, adapter.dump_json(value).decode(), self._ttl)
