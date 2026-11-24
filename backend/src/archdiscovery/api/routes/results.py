import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from archdiscovery.db.session import get_session
from archdiscovery.schemas.results import ApiSpecRead, ArtifactRead, RunResults
from archdiscovery.schemas.run import RunRead
from archdiscovery.services.results import get_run_results

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/runs/{run_id}/results", response_model=RunResults)
def get_results(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> RunResults:
    data = get_run_results(session, run_id)
    return RunResults(
        run=RunRead.model_validate(data["run"]),
        technologies=data["technologies"],
        api_specs=[ApiSpecRead(**spec) for spec in data["api_specs"]],
        deployment=data["deployment"],
        artifacts=[ArtifactRead(**artifact) for artifact in data["artifacts"]],
    )
