import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from archdiscovery.db.session import get_session
from archdiscovery.services.report import get_run_report

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/runs/{run_id}/report")
def get_report(
    run_id: uuid.UUID,
    download: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Единый JSON-отчёт: technologies, api, deployment, api_flows."""
    data = get_run_report(session, run_id)
    report = {
        "technologies": data.get("technologies", []),
        "api": data.get("api", []),
        "deployment": data.get("deployment", []),
        "api_flows": data.get("api_flows", []),
    }
    headers = (
        {"Content-Disposition": f'attachment; filename="report-{run_id}.json"'} if download else {}
    )
    return JSONResponse(content=report, headers=headers)
