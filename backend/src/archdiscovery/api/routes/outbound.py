import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import AnalysisRun, RunArtifact
from archdiscovery.db.session import get_session
from archdiscovery.services.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["syntax"])


@router.get("/runs/{run_id}/outbound-calls")
def get_outbound_calls(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict:
    """Handler → outbound-вызовы (кандидаты P2, без сопоставления с API)."""
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
        return {"available": False, "calls": [], "stats": {}}
    content = artifact.content
    return {
        "available": True,
        "calls": content.get("outbound_calls", []),
        "stats": content.get("stats", {}),
    }
