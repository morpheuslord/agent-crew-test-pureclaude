"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from taskboard_api import __version__
from taskboard_api.api.deps import verify_service_token
from taskboard_api.api.errors import install_error_handlers
from taskboard_api.api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from taskboard_api.api.routers import admin, auth, health, projects, tasks, teams
from taskboard_api.composition import Container
from taskboard_api.config import Settings

# Multipart framing and form fields on top of the largest allowed file.
_BODY_OVERHEAD_BYTES = 1024 * 1024


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or Settings()
    container = container or Container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        container.close()

    app = FastAPI(
        title="Taskboard API",
        version=__version__,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.container = container
    install_error_handlers(app)
    app.add_middleware(
        BodySizeLimitMiddleware, max_bytes=settings.max_upload_bytes + _BODY_OVERHEAD_BYTES
    )
    app.add_middleware(RequestContextMiddleware)

    v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_service_token)])
    for router in (
        auth.router,
        teams.router,
        projects.router,
        tasks.router,
        admin.search_router,
        admin.admin_router,
    ):
        v1.include_router(router)
    app.include_router(v1)
    app.include_router(health.router)
    return app
