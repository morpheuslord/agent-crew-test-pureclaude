"""Time source, injected so services can be tested deterministically."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Returns the current time as an aware UTC datetime."""

    def now(self) -> datetime: ...


class SystemClock:
    """The real wall clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)
