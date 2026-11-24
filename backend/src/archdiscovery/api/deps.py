import uuid
from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from archdiscovery.config import settings
from archdiscovery.crypto import TokenCipher
from archdiscovery.db.session import get_session
from archdiscovery.queue.celery_app import celery_app
from archdiscovery.services.projects import ProjectService
from archdiscovery.services.runs import RunService


def get_cipher() -> TokenCipher:
    return TokenCipher(settings.token_encryption_key)


def get_project_service(
    session: Session = Depends(get_session),
    cipher: TokenCipher = Depends(get_cipher),
) -> ProjectService:
    return ProjectService(session, cipher)


def publish_run_task(run_id: uuid.UUID) -> None:
    celery_app.send_task("pipeline.execute_run", args=[str(run_id)], queue="pipeline")


def get_publisher() -> Callable[[uuid.UUID], None]:
    return publish_run_task


def get_run_service(
    session: Session = Depends(get_session),
    publisher: Callable[[uuid.UUID], None] = Depends(get_publisher),
) -> RunService:
    return RunService(session, publisher)
