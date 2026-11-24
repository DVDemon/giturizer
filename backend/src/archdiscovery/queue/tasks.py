from celery import shared_task


@shared_task(name="pipeline.ping")
def pipeline_ping() -> str:
    """Заглушка P0: проверка, что воркер очереди pipeline жив."""
    return "pong"
