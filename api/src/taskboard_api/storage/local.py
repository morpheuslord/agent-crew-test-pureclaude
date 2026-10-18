"""Attachment storage on a local filesystem volume (development)."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from taskboard_api.storage.interface import CHUNK_SIZE, AttachmentStorage, check_key


class LocalFileStorage(AttachmentStorage):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, stream: IO[bytes]) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as handle:
                shutil.copyfileobj(stream, handle, CHUNK_SIZE)
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def open(self, key: str) -> Iterator[bytes]:
        path = self._path(key)
        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                yield chunk

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def ready(self) -> bool:
        return self._root.is_dir() and os.access(self._root, os.W_OK)

    def _path(self, key: str) -> Path:
        check_key(key)
        path = (self._root / key[:2] / key).resolve()
        if not path.is_relative_to(self._root):
            msg = "storage path escapes the storage root"
            raise ValueError(msg)
        return path
