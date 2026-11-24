import uuid

from fastapi import APIRouter, Depends, Query, status

from archdiscovery.api.deps import get_run_service
from archdiscovery.schemas.run import RunCreate, RunRead
from archdiscovery.services.runs import RunService

router = APIRouter(prefix="/api", tags=["runs"])


@router.post(
    "/projects/{project_id}/runs",
    response_model=RunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(
    project_id: uuid.UUID,
    payload: RunCreate,
    service: RunService = Depends(get_run_service),
) -> RunRead:
    return RunRead.model_validate(service.create(project_id, payload))


@router.get("/projects/{project_id}/runs", response_model=list[RunRead])
def list_runs(
    project_id: uuid.UUID,
    service: RunService = Depends(get_run_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[RunRead]:
    return [
        RunRead.model_validate(item)
        for item in service.list_for_project(project_id, skip=skip, limit=limit)
    ]


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(
    run_id: uuid.UUID,
    service: RunService = Depends(get_run_service),
) -> RunRead:
    return RunRead.model_validate(service.get(run_id))
