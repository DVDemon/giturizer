from archdiscovery.analyzer.celery_app import celery_app as analyzer_app
from archdiscovery.queue.celery_app import celery_app as pipeline_app


def test_pipeline_queue() -> None:
    assert pipeline_app.conf.task_default_queue == "pipeline"


def test_analyzer_queue() -> None:
    assert analyzer_app.conf.task_default_queue == "analyzers"
