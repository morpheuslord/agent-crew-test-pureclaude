"""Comments on tasks."""

from uuid import UUID

from taskboard_api.clock import Clock
from taskboard_api.domain.commands import CommentCommand
from taskboard_api.domain.dtos import CommentDTO
from taskboard_api.domain.enums import ActivityType
from taskboard_api.domain.queries import Principal
from taskboard_api.errors import NotFoundError, PermissionDeniedError
from taskboard_api.models import Comment
from taskboard_api.repositories.interfaces import UnitOfWork
from taskboard_api.services.access import AccessPolicy
from taskboard_api.services.activity import ActivityRecorder
from taskboard_api.services.mappers import comment_dto


class CommentService:
    def __init__(self, *, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock
        self._access = AccessPolicy(uow)
        self._activity = ActivityRecorder(uow, clock)

    def list_comments(self, principal: Principal, task_id: UUID) -> list[CommentDTO]:
        task = self._access.readable_task(principal, task_id).task
        comments = self._uow.comments.list_for_task(task.id)
        users = self._uow.users.get_many(comment.author_id for comment in comments)
        return [comment_dto(comment, users) for comment in comments]

    def add_comment(
        self, principal: Principal, task_id: UUID, command: CommentCommand
    ) -> CommentDTO:
        access = self._access.writable_task(principal, task_id)
        now = self._clock.now()
        comment = Comment(
            task_id=access.task.id,
            author_id=principal.user_id,
            body=command.body,
            created_at=now,
            updated_at=now,
        )
        self._uow.comments.add(comment)
        self._activity.record(
            actor_id=principal.user_id,
            event=ActivityType.COMMENT_ADDED,
            team_id=access.team.id,
            project_id=access.project.id,
            task_id=access.task.id,
            details={"comment_id": str(comment.id)},
        )
        self._uow.commit()
        return self._dto(comment)

    def update_comment(
        self, principal: Principal, comment_id: UUID, command: CommentCommand
    ) -> CommentDTO:
        comment = self._own_comment(principal, comment_id)
        comment.body = command.body
        comment.updated_at = self._clock.now()
        self._uow.commit()
        return self._dto(comment)

    def delete_comment(self, principal: Principal, comment_id: UUID) -> None:
        comment = self._own_comment(principal, comment_id)
        self._uow.comments.delete(comment)
        self._uow.commit()

    def _own_comment(self, principal: Principal, comment_id: UUID) -> Comment:
        comment = self._uow.comments.get(comment_id)
        if comment is None:
            raise NotFoundError("comment not found")
        try:
            self._access.writable_task(principal, comment.task_id)
        except NotFoundError:
            raise NotFoundError("comment not found") from None
        if comment.author_id != principal.user_id:
            raise PermissionDeniedError("only the author can change this comment")
        return comment

    def _dto(self, comment: Comment) -> CommentDTO:
        return comment_dto(comment, self._uow.users.get_many([comment.author_id]))
