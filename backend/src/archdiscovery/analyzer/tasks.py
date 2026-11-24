from pathlib import Path

from celery import shared_task

from archdiscovery.analyzer.cpp import analyze_cpp


@shared_task(name="analyzer.ping")
def analyzer_ping() -> str:
    """Заглушка P0: проверка, что воркер очереди analyzers жив."""
    return "pong"


@shared_task(name="analyzer.cpp")
def analyze_cpp_task(repo_path: str, output_path: str) -> dict:
    """C++-анализатор: doxygen + include-граф; пишет JSON в общий volume."""
    result = analyze_cpp(Path(repo_path), Path(output_path))
    return {"output_path": output_path, "stats": result["stats"]}
