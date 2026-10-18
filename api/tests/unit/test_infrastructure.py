import io
import json
import logging
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError

from taskboard_api.api.http import content_disposition
from taskboard_api.cache.memory import InMemoryCache, NullCache
from taskboard_api.cache.taskboard_cache import TaskboardCache, task_key
from taskboard_api.config import Settings
from taskboard_api.domain.dtos import Page, TaskDTO, TeamDTO
from taskboard_api.errors import PayloadTooLargeError
from taskboard_api.logging_config import JsonFormatter, bind_request_id, configure_logging
from taskboard_api.security.passwords import Argon2PasswordHasher
from taskboard_api.security.rate_limit import FallbackRateLimiter, InMemoryRateLimiter, limiter_key
from taskboard_api.services.export import neutralise
from taskboard_api.services.files import copy_limited, sanitise_content_type, sanitise_filename
from taskboard_api.storage.local import LocalFileStorage
from taskboard_api.storage.s3 import S3Storage

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

KEY = "0123456789abcdef0123456789abcdef"


class Ticker:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_local_storage_roundtrip_and_key_validation(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "files")
    storage.save(KEY, io.BytesIO(b"abc" * 30_000))
    assert b"".join(storage.open(KEY)) == b"abc" * 30_000
    assert (tmp_path / "files" / KEY[:2] / KEY).stat().st_mode & 0o777 == 0o600
    assert storage.ready()
    storage.delete(KEY)
    storage.delete(KEY)
    for bad in ["../../etc/passwd", "ABCDEF" * 6, "", KEY + "/x"]:
        with pytest.raises(ValueError, match="invalid storage key"):
            storage.save(bad, io.BytesIO(b"x"))


def test_local_storage_cleans_up_on_failure(tmp_path: Path) -> None:
    class Exploding(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise OSError("disk on fire")

    storage = LocalFileStorage(tmp_path)
    with pytest.raises(OSError, match="disk on fire"):
        storage.save(KEY, Exploding())
    assert list((tmp_path / KEY[:2]).iterdir()) == []


class FakeS3:
    """Records the calls ``S3Storage`` makes."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[dict[str, Any]] = []
        self.head_ok = True

    # boto3 passes these as capitalised keyword arguments (Bucket=, Key=, ExtraArgs=).
    def upload_fileobj(self, stream: IO[bytes], bucket: str, key: str, **kwargs: Any) -> None:
        self.uploads.append({"bucket": bucket, "key": key, "extra": kwargs["ExtraArgs"]})
        self.objects[key] = stream.read()

    def get_object(self, **kwargs: str) -> dict[str, Any]:
        data = self.objects[kwargs["Key"]]
        return {"Body": StreamingBody(io.BytesIO(data), len(data))}

    def delete_object(self, **kwargs: str) -> None:
        self.objects.pop(kwargs["Key"], None)

    def head_bucket(self, **kwargs: str) -> None:
        if not self.head_ok:
            raise ClientError({"Error": {"Code": "403"}}, "HeadBucket")


@pytest.mark.parametrize(
    ("kms_key", "expected"),
    [
        ("alias/taskboard", {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": "alias/taskboard"}),
        (None, {"ServerSideEncryption": "AES256"}),
    ],
)
def test_s3_storage_encrypts_and_prefixes_keys(
    kms_key: str | None, expected: dict[str, str]
) -> None:
    fake = FakeS3()
    storage = S3Storage(cast("S3Client", fake), "bucket", "attachments/", kms_key_id=kms_key)
    storage.save(KEY, io.BytesIO(b"data"))
    [upload] = fake.uploads
    assert upload["key"] == f"attachments/{KEY}"
    assert upload["extra"] == {"ContentType": "application/octet-stream", **expected}
    assert b"".join(storage.open(KEY)) == b"data"
    assert storage.ready()
    fake.head_ok = False
    assert not storage.ready()
    storage.delete(KEY)
    assert fake.objects == {}
    with pytest.raises(ValueError, match="invalid storage key"):
        storage.save("../x", io.BytesIO(b""))


def test_null_and_memory_cache_counters() -> None:
    null = NullCache()
    null.set("k", "v", 10)
    assert null.get("k") is None
    null.delete("k")
    null.add_to_index("i", "k", 10)
    null.invalidate_index("i")
    assert null.counters().misses == 1
    ticker = Ticker()
    memory = InMemoryCache(clock=ticker)
    memory.set("k", "v", 10)
    assert memory.get("k") == "v"
    ticker.now = 11
    assert memory.get("k") is None
    assert memory.counters().hits == 1
    memory.record_error()
    assert memory.counters().errors == 1


def test_taskboard_cache_index_invalidation_and_corrupt_entries() -> None:
    backend = InMemoryCache()
    cache = TaskboardCache(backend, 60)
    project_id = uuid4()
    page = Page[TaskDTO](items=[], page=1, page_size=20, total=0)
    cache.set_task_page(project_id, "fp1", page)
    cache.set_task_page(project_id, "fp2", page)
    assert cache.get_task_page(project_id, "fp1") == page
    cache.invalidate_project_tasks(project_id)
    assert cache.get_task_page(project_id, "fp2") is None
    user_id = uuid4()
    cache.set_user_teams(user_id, [])
    cache.invalidate_user_lists([user_id], projects=False)
    assert cache.get_user_teams(user_id) is None
    task_id = uuid4()
    backend.set(task_key(task_id), '{"not": "a task"}', 60)
    assert cache.get_task(task_id) is None
    assert task_key(task_id) not in backend.live_keys()
    assert cache.stats().backend == "memory"
    assert TeamDTO.__name__ == "TeamDTO"


def test_rate_limiter_window_and_fallback() -> None:
    ticker = Ticker()
    limiter = InMemoryRateLimiter(clock=ticker)
    assert limiter.hit("k", 2, 60) is None
    assert limiter.hit("k", 2, 60) is None
    assert limiter.hit("k", 2, 60) == 60
    ticker.now = 61
    assert limiter.hit("k", 2, 60) is None

    class Down:
        def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
            raise RedisConnectionError("down")

    fallback = FallbackRateLimiter(Down(), InMemoryRateLimiter())
    assert fallback.hit("k", 1, 60) is None
    assert fallback.hit("k", 1, 60) is not None
    assert limiter_key("login", "A@B.c") == limiter_key("login", "a@b.c")
    assert "a@b.c" not in limiter_key("login", "a@b.c")


def test_argon2_hasher() -> None:
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8)
    hashed = hasher.hash("password 123")
    assert hashed.startswith("$argon2id$")
    assert hasher.verify(hashed, "password 123")
    assert not hasher.verify(hashed, "other")
    assert not hasher.verify("not-a-hash", "password 123")
    hasher.verify_dummy("anything")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("C:\\Users\\me\\secret.docx", "secret.docx"),
        ("../../x\u0000y.txt", "xy.txt"),
        ("..", "attachment"),
        ("   ", "attachment"),
        ("a" * 300, "a" * 255),
    ],
)
def test_sanitise_filename(raw: str, expected: str) -> None:
    assert sanitise_filename(raw) == expected


def test_sanitise_content_type_and_copy_limited() -> None:
    assert sanitise_content_type("image/PNG") == "image/png"
    assert sanitise_content_type("text/html\r\nX-Evil: 1") == "application/octet-stream"
    assert sanitise_content_type(None) == "application/octet-stream"
    with copy_limited(io.BytesIO(b"12345"), 5) as (spool, size):
        assert (spool.read(), size) == (b"12345", 5)
    with pytest.raises(PayloadTooLargeError), copy_limited(io.BytesIO(b"123456"), 5):
        pass


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"])
def test_neutralise_formula_cells(value: str) -> None:
    assert neutralise(value) == "'" + value
    assert neutralise("plain") == "plain"


def test_content_disposition_is_header_safe() -> None:
    header = content_disposition('evil"\r\nSet-Cookie: x=1.html')
    assert "\r" not in header
    assert "\n" not in header
    assert header.startswith('attachment; filename="evil___Set-Cookie_ x_1.html"')
    assert "filename*=UTF-8''evil%22%0D%0ASet-Cookie%3A%20x%3D1.html" in header
    assert 'filename="r_sum_.pdf"' in content_disposition("résumé.pdf")
    assert 'filename="download"' in content_disposition("")


def test_request_id_binding_rejects_unsafe_values() -> None:
    assert bind_request_id("abc-123") == "abc-123"
    generated = bind_request_id("bad id\nwith newline")
    assert len(generated) == 32
    assert bind_request_id(None) != generated


def test_json_formatter_includes_request_id_and_extras() -> None:
    bind_request_id("req-1")
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.user_id = "u1"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "req-1"
    assert payload["user_id"] == "u1"
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "x", None, sys.exc_info())
    assert "boom" in json.loads(JsonFormatter().format(record))["exc_info"]
    configure_logging("INFO")
    assert logging.getLogger().handlers[0].formatter.__class__ is JsonFormatter


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "service_token": "s" * 32,
        "public_ui_url": "http://localhost:3000/",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_settings_validation() -> None:
    settings = _settings()
    assert settings.public_ui_base == "http://localhost:3000"
    with pytest.raises(ValidationError, match="SERVICE_TOKEN"):
        _settings(service_token="short")
    with pytest.raises(ValidationError, match="S3_BUCKET"):
        _settings(storage_backend="s3")
    assert _settings(storage_backend="s3", s3_bucket="b").s3_bucket == "b"
