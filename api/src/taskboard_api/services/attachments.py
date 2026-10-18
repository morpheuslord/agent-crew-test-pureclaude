"""File attachments on tasks."""

import logging
from typing import BinaryIO
from uuid import UUID

from taskboard_api.clock import Clock
from taskboard_api.domain.dtos import AttachmentDownload, AttachmentDTO
from taskboard_api.domain.enums import ActivityType
from taskboard_api.domain.queries import Principal
from taskboard_api.errors import NotFoundError
from taskboard_api.models import Attachment
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.services.access import AccessPolicy
from taskboard_api.services.activity import ActivityRecorder
from taskboard_api.services.files import copy_limited, sanitise_content_type, sanitise_filename
from taskboard_api.services.mappers import attachment_dto
from taskboard_api.storage.interface import AttachmentStorage, new_storage_key

logger = logging.getLogger(__name__)


class AttachmentService:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        storage: AttachmentStorage,
        clock: Clock,
        max_upload_bytes: int,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._clock = clock
        self._max_bytes = max_upload_bytes
        self._access = AccessPolicy(uow)
        self._activity = ActivityRecorder(uow, clock)

    def list_attachments(self, principal: Principal, task_id: UUID) -> list[AttachmentDTO]:
        task = self._access.readable_task(principal, task_id).task
        attachments = self._uow.attachments.list_for_task(task.id)
        users = self._uow.users.get_many(a.uploader_id for a in attachments)
        return [attachment_dto(a, users) for a in attachments]

    def upload(
        self,
        principal: Principal,
        task_id: UUID,
        *,
        filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
    ) -> AttachmentDTO:
        access = self._access.writable_task(principal, task_id)
        key = new_storage_key()
        with copy_limited(stream, self._max_bytes) as (spool, size):
            self._storage.save(key, spool)
        attachment = Attachment(
            task_id=access.task.id,
            uploader_id=principal.user_id,
            filename=sanitise_filename(filename),
            content_type=sanitise_content_type(content_type),
            size_bytes=size,
            storage_key=key,
            created_at=self._clock.now(),
        )
        try:
            self._uow.attachments.add(attachment)
            self._activity.record(
                actor_id=principal.user_id,
                event=ActivityType.ATTACHMENT_ADDED,
                team_id=access.team.id,
                project_id=access.project.id,
                task_id=access.task.id,
                details={"attachment_id": str(attachment.id), "filename": attachment.filename},
            )
            self._uow.commit()
        except Exception:
            self._uow.rollback()
            self._storage.delete(key)
            raise
        return attachment_dto(attachment, self._uow.users.get_many([principal.user_id]))

    def download(self, principal: Principal, attachment_id: UUID) -> AttachmentDownload:
        attachment = self._uow.attachments.get(attachment_id)
        if attachment is None:
            raise NotFoundError("attachment not found")
        try:
            self._access.readable_task(principal, attachment.task_id)
        except NotFoundError:
            raise NotFoundError("attachment not found") from None
        return AttachmentDownload(
            filename=attachment.filename,
            size_bytes=attachment.size_bytes,
            chunks=self._storage.open(attachment.storage_key),
        )
