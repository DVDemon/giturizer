import uuid
from pathlib import Path

from celery import shared_task

from archdiscovery.analyzer.archguard import analyze_archguard
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


@shared_task(name="analyzer.archguard")
def analyze_archguard_task(repo_path: str, output_path: str, languages: list[str]) -> dict:
    """ArchGuard scanner по языкам; пишет сводный JSON в общий volume."""
    result = analyze_archguard(Path(repo_path), Path(output_path), languages)
    return {"output_path": output_path, "summary": result["summary"], "errors": result["errors"]}


@shared_task(name="analyzer.syntax")
def analyze_syntax_task(
    repo_path: str,
    output_path: str,
    languages: list[str],
    run_id: str | None = None,
) -> dict:
    """Tree-sitter syntax-index: endpoint → handler + прогресс по файлам."""
    from archdiscovery.analyzer.syntax.analyze import analyze_syntax
    from archdiscovery.db.models import AnalysisRun
    from archdiscovery.db.session import SessionLocal

    def report(current: int, total: int, message: str) -> None:
        if not run_id:
            return
        try:
            with SessionLocal() as session:
                run = session.get(AnalysisRun, uuid.UUID(run_id))
                if run is None:
                    return
                percent = 30
                if total > 0:
                    percent = 30 + min(15, int(15 * current / total))
                run.progress = percent
                run.progress_detail = {
                    "message": message,
                    "current": current,
                    "total": total,
                    "unit": "files",
                }
                session.commit()
        except Exception:  # noqa: BLE001 - прогресс не должен валить анализ
            return

    result = analyze_syntax(Path(repo_path), Path(output_path), languages, progress=report)
    return {
        "output_path": output_path,
        "stats": result["stats"],
        "errors": result["errors"],
    }
