import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from archdiscovery.api.deps import get_project_service
from archdiscovery.schemas.project import (
    PagedProjects,
    ProjectCreate,
    ProjectListItem,
    ProjectRead,
)
from archdiscovery.services.projects import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return ProjectRead.model_validate(service.create(payload))


@router.get("", response_model=PagedProjects)
def list_projects(
    service: ProjectService = Depends(get_project_service),
    search: str | None = Query(default=None, max_length=255),
    provider: Literal["github", "gitlab", "other"] | None = Query(default=None),
    sort: Literal["last_scan_at", "name", "repo_url", "created_at"] = Query(default="last_scan_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PagedProjects:
    total, rows = service.list_page(
        search=search,
        provider=provider,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
    )
    items = [
        ProjectListItem(
            id=project.id,
            name=project.name,
            repo_url=project.repo_url,
            provider=project.provider,
            default_branch=project.default_branch,
            created_at=project.created_at,
            last_scan_at=last_scan_at,
        )
        for project, last_scan_at in rows
    ]
    return PagedProjects(items=items, total=total, page=page, per_page=per_page)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return ProjectRead.model_validate(service.get(project_id))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
) -> None:
    service.delete(project_id)
