"""Liveness and readiness probes (no authentication, no sensitive detail)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from taskboard_api.composition import ContainerDep

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(container: ContainerDep) -> JSONResponse:
    """Ready when the database and attachment storage work. Redis is optional: reported only."""
    database = container.database_ready()
    storage = container.storage.ready()
    cache = container.cache_backend.available()
    ready = database and storage
    body = {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": "ok" if database else "unavailable",
            "storage": "ok" if storage else "unavailable",
            "cache": "ok" if cache else "degraded",
        },
    }
    return JSONResponse(body, status_code=200 if ready else 503)
