from uuid import UUID

from celery import shared_task

from archdiscovery.db.session import SessionLocal
from archdiscovery.services.runs import execute_stub


@shared_task(name="pipeline.ping")
def pipeline_ping() -> str:
    """Заглушка P0: проверка, что воркер очереди pipeline жив."""
    return "pong"


@shared_task(name="pipeline.execute_run")
def execute_run(run_id: str) -> str:
    """P1: заглушка пайплайна — queued → running → done."""
    with SessionLocal() as session:
        run = execute_stub(session, UUID(run_id))
        return "done" if run is not None else "not_found"
