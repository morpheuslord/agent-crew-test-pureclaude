"""Attachment storage in Amazon S3."""

from collections.abc import Iterator
from typing import IO, TYPE_CHECKING

from botocore.exceptions import BotoCoreError, ClientError

from taskboard_api.storage.interface import CHUNK_SIZE, AttachmentStorage, check_key

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class S3Storage(AttachmentStorage):
    """Objects are private, server-side encrypted (KMS key if configured) and opaque.

    Downloads always go through the API, which enforces authorisation; no presigned URLs.
    """

    def __init__(
        self, client: "S3Client", bucket: str, prefix: str, kms_key_id: str | None = None
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._prefix = prefix
        self._kms_key_id = kms_key_id

    def save(self, key: str, stream: IO[bytes]) -> None:
        extra: dict[str, str] = {"ContentType": "application/octet-stream"}
        if self._kms_key_id:
            extra |= {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self._kms_key_id}
        else:
            extra |= {"ServerSideEncryption": "AES256"}
        self._client.upload_fileobj(stream, self._bucket, self._object_key(key), ExtraArgs=extra)

    def open(self, key: str) -> Iterator[bytes]:
        response = self._client.get_object(Bucket=self._bucket, Key=self._object_key(key))
        body = response["Body"]
        try:
            yield from body.iter_chunks(CHUNK_SIZE)
        finally:
            body.close()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=self._object_key(key))

    def ready(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except (BotoCoreError, ClientError):
            return False
        return True

    def _object_key(self, key: str) -> str:
        return f"{self._prefix}{check_key(key)}"
