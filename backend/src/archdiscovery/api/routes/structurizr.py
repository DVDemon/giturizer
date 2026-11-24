import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from archdiscovery.config import settings
from archdiscovery.db.session import get_session
from archdiscovery.schemas.structurizr import StructurizrArtifact
from archdiscovery.services.c4_graphviz import GraphvizError, render_c4_svg
from archdiscovery.services.graph import Neo4jGraphStore
from archdiscovery.services.structurizr import get_snapshot

router = APIRouter(prefix="/api", tags=["structurizr"])


@router.get("/runs/{run_id}/structurizr", response_model=StructurizrArtifact)
def get_structurizr(
    run_id: uuid.UUID, session: Session = Depends(get_session)
) -> StructurizrArtifact:
    snapshot = get_snapshot(session, run_id)
    return StructurizrArtifact(dsl=snapshot.dsl, workspace=snapshot.workspace)


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


@router.get("/runs/{run_id}/structurizr.dsl", response_class=PlainTextResponse)
def download_dsl(run_id: uuid.UUID, session: Session = Depends(get_session)) -> PlainTextResponse:
    snapshot = get_snapshot(session, run_id)
    return PlainTextResponse(snapshot.dsl, media_type="text/plain")


@router.get("/runs/{run_id}/structurizr.json")
def download_workspace(run_id: uuid.UUID, session: Session = Depends(get_session)) -> JSONResponse:
    snapshot = get_snapshot(session, run_id)
    return JSONResponse(snapshot.workspace)


def _store() -> Neo4jGraphStore:
    return Neo4jGraphStore(settings.neo4j_url, settings.neo4j_user, settings.neo4j_password)


@router.get("/runs/{run_id}/graph/elements")
def graph_elements(run_id: uuid.UUID) -> list[dict]:
    store: Neo4jGraphStore | None = None
    try:
        store = _store()
        return store.elements(str(run_id))
    except Exception as exc:  # noqa: BLE001 - Neo4j недоступен
        raise HTTPException(status_code=503, detail=f"neo4j unavailable: {exc}") from exc
    finally:
        if store is not None:
            store.close()


@router.get("/runs/{run_id}/graph/dependencies")
def graph_dependencies(
    run_id: uuid.UUID,
    element_id: str = Query(..., min_length=1),
    depth: int = Query(3, ge=1, le=10),
) -> list[dict]:
    store: Neo4jGraphStore | None = None
    try:
        store = _store()
        return store.downstream(str(run_id), element_id, depth)
    except Exception as exc:  # noqa: BLE001 - Neo4j недоступен
        raise HTTPException(status_code=503, detail=f"neo4j unavailable: {exc}") from exc
    finally:
        if store is not None:
            store.close()
