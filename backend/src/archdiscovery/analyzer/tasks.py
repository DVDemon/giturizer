from celery import shared_task


@shared_task(name="analyzer.ping")
def analyzer_ping() -> str:
    """Заглушка P0: проверка, что воркер очереди analyzers жив."""
    return "pong"
