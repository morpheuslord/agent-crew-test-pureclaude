"""/api/v1/search and /api/v1/admin."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from taskboard_api.api.deps import PageDep, PrincipalDep, TaskFilterDep
from taskboard_api.composition import AdminServiceDep, TaskServiceDep
from taskboard_api.domain.commands import AdminUpdateUserCommand
from taskboard_api.domain.dtos import ActivityDTO, CacheStatsDTO, Page, TaskSearchItemDTO, UserDTO

search_router = APIRouter(prefix="/search", tags=["search"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@search_router.get("/tasks")
def search_tasks(
    task_filter: TaskFilterDep, principal: PrincipalDep, tasks: TaskServiceDep
) -> Page[TaskSearchItemDTO]:
    return tasks.search_tasks(principal, task_filter)


@admin_router.get("/users")
def list_users(
    page: PageDep,
    principal: PrincipalDep,
    admin: AdminServiceDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[UserDTO]:
    return admin.list_users(principal, page, q)


@admin_router.patch("/users/{user_id}")
def update_user(
    user_id: UUID, body: AdminUpdateUserCommand, principal: PrincipalDep, admin: AdminServiceDep
) -> UserDTO:
    return admin.update_user(principal, user_id, body)


@admin_router.get("/activity")
def global_activity(
    page: PageDep, principal: PrincipalDep, admin: AdminServiceDep
) -> Page[ActivityDTO]:
    return admin.global_activity(principal, page)


@admin_router.get("/cache-stats")
def cache_stats(principal: PrincipalDep, admin: AdminServiceDep) -> CacheStatsDTO:
    return admin.cache_stats(principal)
