from uuid import UUID

from celery import shared_task

from archdiscovery.db.session import SessionLocal
from archdiscovery.services.pipeline import execute_run


@shared_task(name="pipeline.ping")
def pipeline_ping() -> str:
    """Проверка, что воркер очереди pipeline жив."""
    return "pong"


@shared_task(name="pipeline.execute_run")
def execute_run_task(run_id: str) -> str:
    """P2: реальный пайплайн — клон, детект, анализаторы, сохранение результата."""
    with SessionLocal() as session:
        run = execute_run(session, UUID(run_id))
        return run.status.value if run is not None else "not_found"
