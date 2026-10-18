"""/api/v1/projects: project detail, settings, tasks, export and activity."""

from uuid import UUID

from fastapi import APIRouter, Response, status

from taskboard_api.api.deps import PageDep, PrincipalDep, TaskFilterDep
from taskboard_api.api.http import content_disposition
from taskboard_api.composition import ProjectServiceDep, TaskServiceDep
from taskboard_api.domain.commands import CreateTaskCommand, UpdateProjectCommand
from taskboard_api.domain.dtos import ActivityDTO, Page, ProjectDetailDTO, ProjectDTO, TaskDTO

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_my_projects(principal: PrincipalDep, projects: ProjectServiceDep) -> list[ProjectDTO]:
    return projects.list_my_projects(principal)


@router.get("/{project_id}")
def get_project(
    project_id: UUID, principal: PrincipalDep, projects: ProjectServiceDep
) -> ProjectDetailDTO:
    return projects.get_project(principal, project_id)


@router.patch("/{project_id}")
def update_project(
    project_id: UUID,
    body: UpdateProjectCommand,
    principal: PrincipalDep,
    projects: ProjectServiceDep,
) -> ProjectDetailDTO:
    return projects.update_project(principal, project_id, body)


@router.post("/{project_id}/archive")
def archive_project(
    project_id: UUID, principal: PrincipalDep, projects: ProjectServiceDep
) -> ProjectDetailDTO:
    return projects.archive_project(principal, project_id)


@router.get("/{project_id}/tasks")
def list_tasks(
    project_id: UUID, task_filter: TaskFilterDep, principal: PrincipalDep, tasks: TaskServiceDep
) -> Page[TaskDTO]:
    return tasks.list_tasks(principal, project_id, task_filter)


@router.post("/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: UUID, body: CreateTaskCommand, principal: PrincipalDep, tasks: TaskServiceDep
) -> TaskDTO:
    return tasks.create_task(principal, project_id, body)


@router.get("/{project_id}/export.csv", response_class=Response)
def export_csv(project_id: UUID, principal: PrincipalDep, projects: ProjectServiceDep) -> Response:
    name, csv_text = projects.export_csv(principal, project_id)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": content_disposition(f"{name}-tasks.csv"),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{project_id}/activity")
def project_activity(
    project_id: UUID, page: PageDep, principal: PrincipalDep, projects: ProjectServiceDep
) -> Page[ActivityDTO]:
    return projects.project_activity(principal, project_id, page)
