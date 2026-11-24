from celery import Celery

from archdiscovery.config import settings

celery_app = Celery(
    "archdiscovery-analyzer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["archdiscovery.analyzer.tasks"],
)

celery_app.conf.update(
    task_default_queue="analyzers",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
