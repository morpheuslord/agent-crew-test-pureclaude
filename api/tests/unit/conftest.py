"""Services wired with in-memory fakes."""

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import uuid4

import pytest

from taskboard_api.cache.memory import InMemoryCache
from taskboard_api.cache.taskboard_cache import TaskboardCache
from taskboard_api.domain.commands import CreateProjectCommand, CreateTaskCommand, CreateTeamCommand
from taskboard_api.domain.dtos import ProjectDetailDTO, TaskDTO, TeamDTO
from taskboard_api.domain.enums import Role
from taskboard_api.domain.queries import Principal
from taskboard_api.mailer.outbox import OutboxMailer
from taskboard_api.models import TeamMember, User
from taskboard_api.security.rate_limit import InMemoryRateLimiter
from taskboard_api.services.admin import AdminService
from taskboard_api.services.attachments import AttachmentService
from taskboard_api.services.auth import AuthPolicy, AuthService, RateLimitRule
from taskboard_api.services.comments import CommentService
from taskboard_api.services.projects import ProjectService
from taskboard_api.services.tasks import TaskService
from taskboard_api.services.teams import TeamService
from tests.fakes import FakeClock, FakeHasher, FakeUnitOfWork, MemoryStorage, RecordingNotifier

POLICY = AuthPolicy(
    session_ttl=timedelta(hours=12),
    reset_ttl=timedelta(minutes=30),
    public_ui_base="https://taskboard.example",
    login_per_email=RateLimitRule(5, 900),
    login_per_ip=RateLimitRule(50, 900),
    forgot_per_email=RateLimitRule(3, 3600),
    forgot_per_ip=RateLimitRule(20, 3600),
    register_per_ip=RateLimitRule(5, 3600),
    reset_per_ip=RateLimitRule(5, 3600),
)
MAX_UPLOAD = 64


@dataclass
class World:
    uow: FakeUnitOfWork = field(default_factory=FakeUnitOfWork)
    clock: FakeClock = field(default_factory=FakeClock)
    hasher: FakeHasher = field(default_factory=FakeHasher)
    backend: InMemoryCache = field(default_factory=InMemoryCache)
    notifier: RecordingNotifier = field(default_factory=RecordingNotifier)
    storage: MemoryStorage = field(default_factory=MemoryStorage)
    limiter: InMemoryRateLimiter = field(default_factory=InMemoryRateLimiter)

    @property
    def cache(self) -> TaskboardCache:
        return TaskboardCache(self.backend, 300)

    @property
    def auth(self) -> AuthService:
        return AuthService(
            uow=self.uow,
            hasher=self.hasher,
            rate_limiter=self.limiter,
            mailer=OutboxMailer(self.uow.outbox, log_body=False),
            cache=self.cache,
            clock=self.clock,
            policy=POLICY,
        )

    @property
    def admin(self) -> AdminService:
        return AdminService(uow=self.uow, cache=self.cache, clock=self.clock)

    @property
    def teams(self) -> TeamService:
        return TeamService(uow=self.uow, cache=self.cache, clock=self.clock)

    @property
    def projects(self) -> ProjectService:
        return ProjectService(
            uow=self.uow, cache=self.cache, clock=self.clock, webhook_allow_http=False
        )

    @property
    def tasks(self) -> TaskService:
        return TaskService(
            uow=self.uow,
            cache=self.cache,
            clock=self.clock,
            notifier=self.notifier,
            storage=self.storage,
        )

    @property
    def comments(self) -> CommentService:
        return CommentService(uow=self.uow, clock=self.clock)

    @property
    def attachments(self) -> AttachmentService:
        return AttachmentService(
            uow=self.uow, storage=self.storage, clock=self.clock, max_upload_bytes=MAX_UPLOAD
        )

    # Builders --------------------------------------------------------------------------------

    def user(self, name: str, *, role: Role = Role.MEMBER, active: bool = True) -> Principal:
        user = User(
            email=f"{name}@example.com",
            display_name=name.title(),
            password_hash=self.hasher.hash(f"{name}-password"),
            role=role,
            is_active=active,
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.uow.users.add(user)
        self.clock.advance(seconds=1)
        return principal_for(user)

    def team(self, owner: Principal, name: str = "Core") -> TeamDTO:
        return self.teams.create_team(owner, CreateTeamCommand(name=name))

    def join(self, team: TeamDTO, member: Principal) -> None:
        self.uow.teams.add_member(TeamMember(team_id=team.id, user_id=member.user_id))

    def project(
        self,
        owner: Principal,
        team: TeamDTO,
        name: str = "Roadmap",
        webhook_url: str | None = None,
    ) -> ProjectDetailDTO:
        command = CreateProjectCommand(name=name, webhook_url=webhook_url)
        return self.projects.create_project(owner, team.id, command)

    def task(
        self, actor: Principal, project: ProjectDetailDTO, title: str = "Task", **kw: object
    ) -> TaskDTO:
        self.clock.advance(seconds=1)
        return self.tasks.create_task(
            actor, project.id, CreateTaskCommand.model_validate({"title": title, **kw})
        )


def principal_for(user: User) -> Principal:
    return Principal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        session_id=uuid4(),
    )


@pytest.fixture
def world() -> World:
    return World()
