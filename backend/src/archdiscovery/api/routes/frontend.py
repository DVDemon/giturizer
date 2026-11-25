import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import AnalysisRun, RunArtifact
from archdiscovery.db.session import get_session
from archdiscovery.services.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["frontend"])


@router.get("/runs/{run_id}/frontend")
def get_frontend(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict:
    """React frontend API index (Phase 1)."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    artifact = session.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id == run_id,
            RunArtifact.kind == "frontend",
        )
    ).first()
    if artifact is None or not isinstance(artifact.content, dict):
        return {
            "available": False,
            "frontends": [],
            "api_calls": [],
            "stats": {},
            "errors": [],
        }
    content = artifact.content
    return {
        "available": True,
        "frontends": content.get("frontends", []),
        "api_calls": content.get("api_calls", []),
        "stats": content.get("stats", {}),
        "errors": content.get("errors", []),
    }
