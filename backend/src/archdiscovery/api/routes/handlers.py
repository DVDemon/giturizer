import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import AnalysisRun, RunArtifact
from archdiscovery.db.session import get_session
from archdiscovery.services.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["syntax"])


@router.get("/runs/{run_id}/handlers")
def get_handlers(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict:
    """Endpoint → handler, найденные Tree-sitter для запуска."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    artifact = session.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id == run_id,
            RunArtifact.kind == "syntax",
        )
    ).first()
    if artifact is None or not isinstance(artifact.content, dict):
        return {"available": False, "handlers": [], "stats": {}, "errors": []}
    content = artifact.content
    return {
        "available": True,
        "handlers": content.get("handlers", []),
        "stats": content.get("stats", {}),
        "errors": content.get("errors", []),
    }
