from celery import Celery

from archdiscovery.config import settings

celery_app = Celery(
    "archdiscovery-pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["archdiscovery.queue.tasks"],
)

celery_app.conf.update(
    task_default_queue="pipeline",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
