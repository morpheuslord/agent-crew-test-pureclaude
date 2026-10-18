"""Domain errors.

Services raise these; ``taskboard_api.api.errors`` maps them to HTTP responses in one place.
"""

from collections.abc import Mapping


class DomainError(Exception):
    """Base class for all expected, user-facing failures."""

    code = "error"

    def __init__(self, message: str, fields: Mapping[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields: dict[str, str] = dict(fields or {})


class NotFoundError(DomainError):
    """The resource does not exist or the caller is not allowed to know it exists."""

    code = "not_found"


class PermissionDeniedError(DomainError):
    """The caller can see the resource but may not perform the action."""

    code = "forbidden"


class AuthenticationError(DomainError):
    """Missing, invalid or expired credentials."""

    code = "unauthenticated"


class ConflictError(DomainError):
    """The request conflicts with the current state (duplicate, archived project, ...)."""

    code = "conflict"


class ValidationFailedError(DomainError):
    """Input is well-formed but violates a business rule."""

    code = "validation_failed"


class RateLimitedError(DomainError):
    """Too many attempts in the current window."""

    code = "rate_limited"

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class PayloadTooLargeError(DomainError):
    """An upload exceeds the configured size limit."""

    code = "payload_too_large"
