"""The one place where exceptions become HTTP responses."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskboard_api.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
    RateLimitedError,
    ValidationFailedError,
)

logger = logging.getLogger(__name__)

_STATUS: dict[type[DomainError], int] = {
    NotFoundError: 404,
    PermissionDeniedError: 403,
    AuthenticationError: 401,
    ConflictError: 409,
    ValidationFailedError: 422,
    RateLimitedError: 429,
    PayloadTooLargeError: 413,
}


def error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


def _status_for(exc: DomainError) -> int:
    for cls in type(exc).__mro__:
        if cls in _STATUS:
            return _STATUS[cls]
    return 400


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = _status_for(exc)
    headers: dict[str, str] = {}
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = "Bearer"
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(error_body(exc.code, exc.message, exc.fields), status, headers=headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part not in {"body", "query"}]
        # Only the message is returned: echoing the input could reflect passwords back.
        fields[".".join(location) or "request"] = str(error.get("msg", "invalid"))
    return JSONResponse(error_body("validation_failed", "the request is invalid", fields), 422)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = "payload_too_large" if exc.status_code == 413 else "http_error"
    return JSONResponse(error_body(code, str(exc.detail)), exc.status_code, headers=exc.headers)


async def _integrity_error(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("integrity error", extra={"error_type": type(exc).__name__})
    return JSONResponse(error_body("conflict", "the request conflicts with existing data"), 409)


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error", exc_info=exc)
    return JSONResponse(error_body("internal_error", "an unexpected error occurred"), 500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(IntegrityError, _integrity_error)
    app.add_exception_handler(Exception, _unexpected_error)
