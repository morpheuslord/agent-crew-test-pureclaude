"""Helpers for handling uploaded files safely."""

import re
import tempfile
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, BinaryIO

from taskboard_api.errors import PayloadTooLargeError
from taskboard_api.storage.interface import CHUNK_SIZE

MAX_FILENAME_LENGTH = 255
DEFAULT_CONTENT_TYPE = "application/octet-stream"
_CONTENT_TYPE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]{1,64}/[A-Za-z0-9!#$&^_.+-]{1,127}$")
_SPOOL_IN_MEMORY = 1024 * 1024


def sanitise_filename(raw: str | None) -> str:
    """Keep only the last path component, without control characters, at most 255 characters."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    name = name[:MAX_FILENAME_LENGTH]
    if name in {"", ".", ".."}:
        return "attachment"
    return name


def sanitise_content_type(raw: str | None) -> str:
    """Accept a plain ``type/subtype``; parameters and anything unusual become the default."""
    value = (raw or "").split(";", 1)[0].strip().lower()
    return value if _CONTENT_TYPE.fullmatch(value) else DEFAULT_CONTENT_TYPE


@contextmanager
def copy_limited(source: BinaryIO, max_bytes: int) -> Iterator[tuple[IO[bytes], int]]:
    """Copy ``source`` into a spooled temporary file, failing as soon as it exceeds ``max_bytes``.

    The size is counted from the bytes actually read, never from a client-declared length. The
    temporary file is closed when the ``with`` block ends.
    """
    with tempfile.SpooledTemporaryFile(max_size=_SPOOL_IN_MEMORY) as spool:
        size = 0
        while chunk := source.read(CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise PayloadTooLargeError(f"files can be at most {max_bytes // (1024 * 1024)} MB")
            spool.write(chunk)
        spool.seek(0)
        yield spool, size
