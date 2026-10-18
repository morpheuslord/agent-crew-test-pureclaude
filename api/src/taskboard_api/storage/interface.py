"""Attachment storage interface."""

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import IO

CHUNK_SIZE = 64 * 1024
_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def new_storage_key() -> str:
    """A random key. Storage keys never contain user input."""
    return uuid.uuid4().hex


def check_key(key: str) -> str:
    """Reject anything that is not a key produced by ``new_storage_key``."""
    if not _KEY_PATTERN.fullmatch(key):
        msg = "invalid storage key"
        raise ValueError(msg)
    return key


class AttachmentStorage(ABC):
    """Stores attachment bytes by opaque key."""

    @abstractmethod
    def save(self, key: str, stream: IO[bytes]) -> None:
        """Store the whole stream under ``key``."""

    @abstractmethod
    def open(self, key: str) -> Iterator[bytes]:
        """Yield the stored bytes in chunks."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object; missing objects are ignored."""

    @abstractmethod
    def ready(self) -> bool:
        """Whether the backend is usable (for readiness checks)."""
