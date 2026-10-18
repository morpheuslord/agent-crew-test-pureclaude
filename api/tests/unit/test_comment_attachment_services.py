import io
from uuid import uuid4

import pytest

from taskboard_api.domain.commands import CommentCommand
from taskboard_api.domain.enums import ActivityType
from taskboard_api.errors import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
)
from tests.unit.conftest import MAX_UPLOAD, World


def test_comments_lifecycle_and_author_only_edits(world: World) -> None:
    owner = world.user("olive")
    bob = world.user("bob")
    team = world.team(owner)
    world.join(team, bob)
    task = world.task(owner, world.project(owner, team))
    comment = world.comments.add_comment(bob, task.id, CommentCommand(body="**hi**"))
    assert comment.author_name == "Bob"
    assert world.uow.store.activity[-1].event_type is ActivityType.COMMENT_ADDED
    with pytest.raises(PermissionDeniedError):
        world.comments.update_comment(owner, comment.id, CommentCommand(body="hijack"))
    with pytest.raises(PermissionDeniedError):
        world.comments.delete_comment(owner, comment.id)
    world.clock.advance(minutes=1)
    edited = world.comments.update_comment(bob, comment.id, CommentCommand(body="edited"))
    assert edited.body == "edited"
    assert edited.updated_at > edited.created_at
    assert [c.body for c in world.comments.list_comments(owner, task.id)] == ["edited"]
    world.comments.delete_comment(bob, comment.id)
    assert world.comments.list_comments(owner, task.id) == []


def test_comments_hidden_from_non_members_and_locked_when_archived(world: World) -> None:
    owner = world.user("olive")
    project = world.project(owner, world.team(owner))
    task = world.task(owner, project)
    comment = world.comments.add_comment(owner, task.id, CommentCommand(body="note"))
    mallory = world.user("mallory")
    with pytest.raises(NotFoundError):
        world.comments.list_comments(mallory, task.id)
    with pytest.raises(NotFoundError):
        world.comments.update_comment(mallory, comment.id, CommentCommand(body="x"))
    with pytest.raises(NotFoundError):
        world.comments.delete_comment(owner, uuid4())
    world.projects.archive_project(owner, project.id)
    with pytest.raises(ConflictError):
        world.comments.add_comment(owner, task.id, CommentCommand(body="late"))
    with pytest.raises(ConflictError):
        world.comments.update_comment(owner, comment.id, CommentCommand(body="late"))


def test_upload_list_and_download(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    dto = world.attachments.upload(
        owner,
        task.id,
        filename="../../etc/passwd\r\n.txt",
        content_type="text/html; charset=utf-8",
        stream=io.BytesIO(b"hello world"),
    )
    assert dto.filename == "passwd.txt"
    assert dto.content_type == "text/html"
    assert dto.size_bytes == 11
    stored = world.uow.attachments.get(dto.id)
    assert stored is not None
    assert "/" not in stored.storage_key
    assert [a.id for a in world.attachments.list_attachments(owner, task.id)] == [dto.id]
    download = world.attachments.download(owner, dto.id)
    assert b"".join(download.chunks) == b"hello world"
    assert world.uow.store.activity[-1].event_type is ActivityType.ATTACHMENT_ADDED


def test_upload_over_limit_is_rejected_and_nothing_is_stored(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    with pytest.raises(PayloadTooLargeError):
        world.attachments.upload(
            owner,
            task.id,
            filename="big.bin",
            content_type=None,
            stream=io.BytesIO(b"x" * (MAX_UPLOAD + 1)),
        )
    assert world.storage.objects == {}
    assert world.uow.store.attachments == {}


def test_failed_commit_removes_stored_bytes(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    world.uow.fail_next_commit = True
    with pytest.raises(RuntimeError):
        world.attachments.upload(
            owner, task.id, filename="a.txt", content_type=None, stream=io.BytesIO(b"abc")
        )
    assert world.storage.objects == {}
    assert world.uow.rollbacks == 1


def test_attachments_are_not_visible_to_non_members(world: World) -> None:
    owner = world.user("olive")
    task = world.task(owner, world.project(owner, world.team(owner)))
    dto = world.attachments.upload(
        owner, task.id, filename=None, content_type=None, stream=io.BytesIO(b"abc")
    )
    assert dto.filename == "attachment"
    assert dto.content_type == "application/octet-stream"
    mallory = world.user("mallory")
    with pytest.raises(NotFoundError):
        world.attachments.download(mallory, dto.id)
    with pytest.raises(NotFoundError):
        world.attachments.list_attachments(mallory, task.id)
    with pytest.raises(NotFoundError):
        world.attachments.upload(
            mallory, task.id, filename="x", content_type=None, stream=io.BytesIO(b"")
        )
    with pytest.raises(NotFoundError):
        world.attachments.download(owner, task.id)
