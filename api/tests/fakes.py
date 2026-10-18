"""In-memory implementations of the repository and infrastructure interfaces."""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import IO, Any
from uuid import UUID

from taskboard_api.domain.enums import PRIORITY_RANK, STATUS_RANK, SortField, SortOrder
from taskboard_api.domain.queries import PageRequest, TaskFilter
from taskboard_api.models import (
    Activity,
    Attachment,
    Comment,
    OutboxMessage,
    PasswordResetToken,
    Project,
    Task,
    Team,
    TeamMember,
    User,
    UserSession,
)
from taskboard_api.repositories.interfaces import (
    ActivityRepository,
    AttachmentRepository,
    CommentRepository,
    OutboxRepository,
    PasswordResetRepository,
    ProjectRepository,
    SessionRepository,
    TaskRepository,
    TeamRepository,
    UserRepository,
)
from taskboard_api.storage.interface import AttachmentStorage, check_key
from taskboard_api.webhooks.sender import WebhookDelivery


@dataclass
class Store:
    users: dict[UUID, User] = field(default_factory=dict)
    sessions: dict[UUID, UserSession] = field(default_factory=dict)
    reset_tokens: dict[UUID, PasswordResetToken] = field(default_factory=dict)
    outbox: list[OutboxMessage] = field(default_factory=list)
    teams: dict[UUID, Team] = field(default_factory=dict)
    members: dict[tuple[UUID, UUID], TeamMember] = field(default_factory=dict)
    projects: dict[UUID, Project] = field(default_factory=dict)
    tasks: dict[UUID, Task] = field(default_factory=dict)
    comments: dict[UUID, Comment] = field(default_factory=dict)
    attachments: dict[UUID, Attachment] = field(default_factory=dict)
    activity: list[Activity] = field(default_factory=list)


def _page[T](items: list[T], page: PageRequest) -> tuple[list[T], int]:
    return items[page.offset : page.offset + page.page_size], len(items)


class FakeUserRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, user: User) -> None:
        self._s.users[user.id] = user

    def get(self, user_id: UUID) -> User | None:
        return self._s.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._s.users.values() if u.email == email), None)

    def get_many(self, user_ids: Iterable[UUID]) -> dict[UUID, User]:
        return {i: self._s.users[i] for i in set(user_ids) if i in self._s.users}

    def list(self, page: PageRequest, query: str | None) -> tuple[list[User], int]:
        users = sorted(self._s.users.values(), key=lambda u: (u.created_at, u.id))
        if query:
            needle = query.lower()
            users = [
                u for u in users if needle in u.email.lower() or needle in u.display_name.lower()
            ]
        return _page(users, page)


class FakeSessionRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, session: UserSession) -> None:
        self._s.sessions[session.id] = session

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        return next((s for s in self._s.sessions.values() if s.token_hash == token_hash), None)

    def delete(self, session_id: UUID) -> None:
        self._s.sessions.pop(session_id, None)

    def delete_for_user(self, user_id: UUID, *, keep: UUID | None = None) -> None:
        for sid, session in list(self._s.sessions.items()):
            if session.user_id == user_id and sid != keep:
                del self._s.sessions[sid]

    def delete_expired(self, now: datetime) -> None:
        for sid, session in list(self._s.sessions.items()):
            if session.expires_at <= now:
                del self._s.sessions[sid]


class FakePasswordResetRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, token: PasswordResetToken) -> None:
        self._s.reset_tokens[token.id] = token

    def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        return next((t for t in self._s.reset_tokens.values() if t.token_hash == token_hash), None)

    def invalidate_for_user(self, user_id: UUID, now: datetime) -> None:
        for token in self._s.reset_tokens.values():
            if token.user_id == user_id and token.used_at is None:
                token.used_at = now


class FakeOutboxRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, message: OutboxMessage) -> None:
        self._s.outbox.append(message)

    def list_for(self, to_address: str) -> list[OutboxMessage]:
        return [m for m in self._s.outbox if m.to_address == to_address]


class FakeTeamRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, team: Team) -> None:
        self._s.teams[team.id] = team

    def get(self, team_id: UUID) -> Team | None:
        return self._s.teams.get(team_id)

    def list_for_user(self, user_id: UUID) -> list[Team]:
        ids = {t for (t, u) in self._s.members if u == user_id}
        return sorted((self._s.teams[i] for i in ids), key=lambda t: (t.name, t.id))

    def add_member(self, member: TeamMember) -> None:
        self._s.members[(member.team_id, member.user_id)] = member

    def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        self._s.members.pop((team_id, user_id), None)

    def get_member(self, team_id: UUID, user_id: UUID) -> TeamMember | None:
        return self._s.members.get((team_id, user_id))

    def list_members(self, team_id: UUID) -> list[tuple[TeamMember, User]]:
        rows = [(m, self._s.users[u]) for (t, u), m in self._s.members.items() if t == team_id]
        return sorted(rows, key=lambda row: (row[1].display_name, row[1].id))

    def member_ids(self, team_id: UUID) -> list[UUID]:
        return [u for (t, u) in self._s.members if t == team_id]


class FakeProjectRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, project: Project) -> None:
        self._s.projects[project.id] = project

    def get(self, project_id: UUID) -> Project | None:
        return self._s.projects.get(project_id)

    def get_many(self, project_ids: Iterable[UUID]) -> dict[UUID, Project]:
        return {i: self._s.projects[i] for i in set(project_ids) if i in self._s.projects}

    def list_for_team(self, team_id: UUID) -> list[Project]:
        return self.list_for_teams([team_id])

    def list_for_teams(self, team_ids: Sequence[UUID]) -> list[Project]:
        rows = [p for p in self._s.projects.values() if p.team_id in set(team_ids)]
        return sorted(rows, key=lambda p: (p.archived, p.name, p.id))


_SORT_KEYS: dict[SortField, Callable[[Task], Any]] = {
    SortField.TITLE: lambda t: t.title,
    SortField.DESCRIPTION: lambda t: t.description,
    SortField.STATUS: lambda t: STATUS_RANK[t.status],
    SortField.PRIORITY: lambda t: PRIORITY_RANK[t.priority],
    SortField.ASSIGNEE_ID: lambda t: t.assignee_id,
    SortField.DUE_DATE: lambda t: t.due_date,
    SortField.LABELS: lambda t: t.labels,
    SortField.CREATED_AT: lambda t: t.created_at,
    SortField.UPDATED_AT: lambda t: t.updated_at,
}


class FakeTaskRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, task: Task) -> None:
        self._s.tasks[task.id] = task

    def get(self, task_id: UUID) -> Task | None:
        return self._s.tasks.get(task_id)

    def delete(self, task: Task) -> None:
        self._s.tasks.pop(task.id, None)
        for cid in [c.id for c in self._s.comments.values() if c.task_id == task.id]:
            del self._s.comments[cid]
        for aid in [a.id for a in self._s.attachments.values() if a.task_id == task.id]:
            del self._s.attachments[aid]

    def search(self, task_filter: TaskFilter) -> tuple[list[Task], int]:
        f = task_filter
        rows = list(self._s.tasks.values())
        if f.project_ids is not None:
            rows = [t for t in rows if t.project_id in f.project_ids]
        if f.text:
            needle = f.text.lower()
            rows = [t for t in rows if needle in t.title.lower() or needle in t.description.lower()]
        if f.status is not None:
            rows = [t for t in rows if t.status == f.status]
        if f.assignee_id is not None:
            rows = [t for t in rows if t.assignee_id == f.assignee_id]
        if f.label:
            rows = [t for t in rows if f.label in t.labels]
        if f.due_before is not None:
            due = f.due_before
            rows = [t for t in rows if t.due_date is not None and t.due_date < due]
        key = _SORT_KEYS[f.sort]
        present = sorted((t for t in rows if key(t) is not None), key=lambda t: t.id)
        present.sort(key=key, reverse=f.order is SortOrder.DESC)
        missing = sorted((t for t in rows if key(t) is None), key=lambda t: t.id)
        return _page(present + missing, f.page)

    def list_for_project(self, project_id: UUID) -> list[Task]:
        rows = [t for t in self._s.tasks.values() if t.project_id == project_id]
        return sorted(rows, key=lambda t: (t.created_at, t.id))

    def unassign(self, project_ids: Sequence[UUID], user_id: UUID) -> list[Task]:
        changed = [
            t
            for t in self._s.tasks.values()
            if t.project_id in set(project_ids) and t.assignee_id == user_id
        ]
        for task in changed:
            task.assignee_id = None
        return changed


class FakeCommentRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, comment: Comment) -> None:
        self._s.comments[comment.id] = comment

    def get(self, comment_id: UUID) -> Comment | None:
        return self._s.comments.get(comment_id)

    def delete(self, comment: Comment) -> None:
        self._s.comments.pop(comment.id, None)

    def list_for_task(self, task_id: UUID) -> list[Comment]:
        rows = [c for c in self._s.comments.values() if c.task_id == task_id]
        return sorted(rows, key=lambda c: (c.created_at, c.id))


class FakeAttachmentRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, attachment: Attachment) -> None:
        self._s.attachments[attachment.id] = attachment

    def get(self, attachment_id: UUID) -> Attachment | None:
        return self._s.attachments.get(attachment_id)

    def list_for_task(self, task_id: UUID) -> list[Attachment]:
        rows = [a for a in self._s.attachments.values() if a.task_id == task_id]
        return sorted(rows, key=lambda a: (a.created_at, a.id))


class FakeActivityRepository:
    def __init__(self, store: Store) -> None:
        self._s = store

    def add(self, activity: Activity) -> None:
        self._s.activity.append(activity)

    def _sorted(self, rows: list[Activity]) -> list[Activity]:
        by_id = sorted(rows, key=lambda a: a.id)
        return sorted(by_id, key=lambda a: a.created_at, reverse=True)

    def list_for_project(
        self, project_id: UUID, team_id: UUID, page: PageRequest
    ) -> tuple[list[Activity], int]:
        rows = [
            a
            for a in self._s.activity
            if a.project_id == project_id or (a.team_id == team_id and a.project_id is None)
        ]
        return _page(self._sorted(rows), page)

    def list_all(self, page: PageRequest) -> tuple[list[Activity], int]:
        return _page(self._sorted(list(self._s.activity)), page)


class FakeUnitOfWork:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()
        self.users: UserRepository = FakeUserRepository(self.store)
        self.sessions: SessionRepository = FakeSessionRepository(self.store)
        self.reset_tokens: PasswordResetRepository = FakePasswordResetRepository(self.store)
        self.outbox: OutboxRepository = FakeOutboxRepository(self.store)
        self.teams: TeamRepository = FakeTeamRepository(self.store)
        self.projects: ProjectRepository = FakeProjectRepository(self.store)
        self.tasks: TaskRepository = FakeTaskRepository(self.store)
        self.comments: CommentRepository = FakeCommentRepository(self.store)
        self.attachments: AttachmentRepository = FakeAttachmentRepository(self.store)
        self.activity: ActivityRepository = FakeActivityRepository(self.store)
        self.commits = 0
        self.rollbacks = 0
        self.fail_next_commit = False

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        if self.fail_next_commit:
            self.fail_next_commit = False
            msg = "simulated commit failure"
            raise RuntimeError(msg)
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeHasher:
    """Reversible "hash" so tests run fast; records dummy verifications."""

    def __init__(self) -> None:
        self.dummy_calls = 0

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"hashed:{password}"

    def verify_dummy(self, password: str) -> None:
        self.dummy_calls += 1


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 10, 18, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


class RecordingNotifier:
    def __init__(self) -> None:
        self.deliveries: list[WebhookDelivery] = []
        self.closed = False

    def notify(self, delivery: WebhookDelivery) -> None:
        self.deliveries.append(delivery)

    def close(self) -> None:
        self.closed = True


class MemoryStorage(AttachmentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_delete = False

    def save(self, key: str, stream: IO[bytes]) -> None:
        self.objects[check_key(key)] = stream.read()

    def open(self, key: str) -> Iterator[bytes]:
        data = self.objects[check_key(key)]
        yield from (data[i : i + 4] for i in range(0, len(data), 4))

    def delete(self, key: str) -> None:
        if self.fail_delete:
            msg = "storage unavailable"
            raise OSError(msg)
        self.objects.pop(check_key(key), None)

    def ready(self) -> bool:
        return True
