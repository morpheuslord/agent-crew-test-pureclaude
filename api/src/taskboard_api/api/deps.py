"""Request-level dependencies: service authentication, caller identity, query parameters."""

import ipaddress
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query, Request

from taskboard_api.composition import AuthServiceDep, ContainerDep
from taskboard_api.domain.enums import SortField, SortOrder, TaskStatus
from taskboard_api.domain.queries import (
    MAX_PAGE_SIZE,
    MAX_SEARCH_TEXT,
    PageRequest,
    Principal,
    TaskFilter,
)
from taskboard_api.errors import AuthenticationError
from taskboard_api.security.tokens import constant_time_equals


def verify_service_token(
    container: ContainerDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Every /api/v1 call must come from the UI server, which holds the shared service token."""
    expected = container.settings.service_token.get_secret_value()
    if x_service_token is None or not constant_time_equals(x_service_token, expected):
        raise AuthenticationError("service authentication required")


def get_principal(
    auth: AuthServiceDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    token = None
    if authorization is not None:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value.strip()
    return auth.authenticate(token)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def get_client_ip(
    request: Request,
    x_client_ip: Annotated[str | None, Header()] = None,
) -> str:
    """The browser's address as reported by the authenticated UI server, used for rate limits."""
    if x_client_ip:
        try:
            return str(ipaddress.ip_address(x_client_ip.strip()))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


ClientIpDep = Annotated[str, Depends(get_client_ip)]


def get_page(
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> PageRequest:
    return PageRequest(page=page, page_size=page_size)


PageDep = Annotated[PageRequest, Depends(get_page)]


def get_task_filter(
    page: PageDep,
    q: Annotated[str | None, Query(max_length=MAX_SEARCH_TEXT)] = None,
    status: TaskStatus | None = None,
    assignee_id: UUID | None = None,
    label: Annotated[str | None, Query(max_length=40)] = None,
    due_before: date | None = None,
    sort: SortField = SortField.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
) -> TaskFilter:
    """Sort field and direction are enums, so unknown values are rejected with 422."""
    return TaskFilter(
        text=q.strip() or None if q else None,
        status=status,
        assignee_id=assignee_id,
        label=label.strip().lower() or None if label else None,
        due_before=due_before,
        sort=sort,
        order=order,
        page=page,
    )


TaskFilterDep = Annotated[TaskFilter, Depends(get_task_filter)]
