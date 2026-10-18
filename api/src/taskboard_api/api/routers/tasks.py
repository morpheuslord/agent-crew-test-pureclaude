"""/api/v1/tasks, /comments and /attachments."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import StreamingResponse

from taskboard_api.api.deps import PrincipalDep
from taskboard_api.api.http import content_disposition
from taskboard_api.composition import AttachmentServiceDep, CommentServiceDep, TaskServiceDep
from taskboard_api.domain.commands import CommentCommand, UpdateTaskCommand
from taskboard_api.domain.dtos import AttachmentDTO, CommentDTO, TaskDTO

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}")
def get_task(task_id: UUID, principal: PrincipalDep, tasks: TaskServiceDep) -> TaskDTO:
    return tasks.get_task(principal, task_id)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: UUID, body: UpdateTaskCommand, principal: PrincipalDep, tasks: TaskServiceDep
) -> TaskDTO:
    return tasks.update_task(principal, task_id, body)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, principal: PrincipalDep, tasks: TaskServiceDep) -> None:
    tasks.delete_task(principal, task_id)


@router.get("/tasks/{task_id}/comments")
def list_comments(
    task_id: UUID, principal: PrincipalDep, comments: CommentServiceDep
) -> list[CommentDTO]:
    return comments.list_comments(principal, task_id)


@router.post("/tasks/{task_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: UUID, body: CommentCommand, principal: PrincipalDep, comments: CommentServiceDep
) -> CommentDTO:
    return comments.add_comment(principal, task_id, body)


@router.patch("/comments/{comment_id}")
def update_comment(
    comment_id: UUID, body: CommentCommand, principal: PrincipalDep, comments: CommentServiceDep
) -> CommentDTO:
    return comments.update_comment(principal, comment_id, body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: UUID, principal: PrincipalDep, comments: CommentServiceDep) -> None:
    comments.delete_comment(principal, comment_id)


@router.get("/tasks/{task_id}/attachments")
def list_attachments(
    task_id: UUID, principal: PrincipalDep, attachments: AttachmentServiceDep
) -> list[AttachmentDTO]:
    return attachments.list_attachments(principal, task_id)


@router.post("/tasks/{task_id}/attachments", status_code=status.HTTP_201_CREATED)
def upload_attachment(
    task_id: UUID,
    file: Annotated[UploadFile, File()],
    principal: PrincipalDep,
    attachments: AttachmentServiceDep,
) -> AttachmentDTO:
    return attachments.upload(
        principal,
        task_id,
        filename=file.filename,
        content_type=file.content_type,
        stream=file.file,
    )


@router.get("/attachments/{attachment_id}/download", response_class=StreamingResponse)
def download_attachment(
    attachment_id: UUID, principal: PrincipalDep, attachments: AttachmentServiceDep
) -> StreamingResponse:
    download = attachments.download(principal, attachment_id)
    return StreamingResponse(
        download.chunks,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": content_disposition(download.filename),
            "Content-Length": str(download.size_bytes),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
