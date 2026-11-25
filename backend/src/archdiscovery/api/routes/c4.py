import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from archdiscovery.db.session import get_session
from archdiscovery.services.c4_graphviz import GraphvizError, render_c4_svg
from archdiscovery.services.structurizr import get_snapshot

router = APIRouter(prefix="/api", tags=["c4"])


@router.get("/runs/{run_id}/c4.svg", response_class=Response)
def get_c4_svg(run_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    """Container-диаграмма C4, отрендеренная Graphviz."""
    snapshot = get_snapshot(session, run_id)
    try:
        svg = render_c4_svg(snapshot.workspace)
    except GraphvizError as exc:
        raise HTTPException(status_code=503, detail=f"graphviz unavailable: {exc}") from exc
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/runs/{run_id}/c4.model")
def get_c4_model(run_id: uuid.UUID, session: Session = Depends(get_session)) -> JSONResponse:
    """Минимальная C4-модель для Mermaid; не является Structurizr workspace."""
    snapshot = get_snapshot(session, run_id)
    model = snapshot.workspace.get("model") or {}
    return JSONResponse(
        {
            "softwareSystems": model.get("softwareSystems") or [],
            "relationships": model.get("relationships") or [],
        }
    )
