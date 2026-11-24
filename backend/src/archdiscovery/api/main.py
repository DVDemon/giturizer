import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from archdiscovery import __version__
from archdiscovery.api.routes import health, projects, results, runs
from archdiscovery.config import settings
from archdiscovery.logging import configure_logging
from archdiscovery.services.errors import DispatchError, NotFoundError

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("ArchDiscovery API started (version=%s)", __version__)
    yield
    logger.info("ArchDiscovery API stopped")


app = FastAPI(title="ArchDiscovery API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(results.router)


@app.exception_handler(NotFoundError)
async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DispatchError)
async def handle_dispatch_error(_: Request, exc: DispatchError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": f"queue unavailable: {exc}"})
