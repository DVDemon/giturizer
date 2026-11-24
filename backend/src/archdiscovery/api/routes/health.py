from fastapi import APIRouter
from pydantic import BaseModel

from archdiscovery import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="archdiscovery-api", version=__version__)
