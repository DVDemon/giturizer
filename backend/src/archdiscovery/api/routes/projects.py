import uuid

from fastapi import APIRouter, Depends, Query, status

from archdiscovery.api.deps import get_project_service
from archdiscovery.schemas.project import ProjectCreate, ProjectRead
from archdiscovery.services.projects import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return ProjectRead.model_validate(service.create(payload))


@router.get("", response_model=list[ProjectRead])
def list_projects(
    service: ProjectService = Depends(get_project_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[ProjectRead]:
    return [ProjectRead.model_validate(item) for item in service.list(skip=skip, limit=limit)]


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
