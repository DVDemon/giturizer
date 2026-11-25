import json
from pathlib import Path

from archdiscovery.config import settings
from archdiscovery.queue.celery_app import celery_app


def dispatch_cpp_analyzer(repo_path: Path, artifacts_dir: Path, timeout: int | None = None) -> dict:
    """Ставит задачу анализа C++ в очередь analyzers и ждёт результат."""
    output = artifacts_dir / "cpp.json"
    async_result = celery_app.send_task(
        "analyzer.cpp",
        args=[str(repo_path), str(output)],
        queue="analyzers",
    )
    # Пайплайн намеренно ждёт анализатор последовательно; Celery по умолчанию
    # запрещает блокирующий get() внутри задачи — снимаем этот запрет явно.
    async_result.get(timeout=timeout or settings.analyzer_timeout, disable_sync_subtasks=False)
    if not output.exists():
        raise RuntimeError("C++ analyzer produced no output")
    return json.loads(output.read_text(encoding="utf-8"))


def dispatch_archguard_analyzer(
    repo_path: Path,
    artifacts_dir: Path,
    languages: list[str],
    timeout: int | None = None,
) -> dict:
    """Ставит задачу ArchGuard (по языкам) в очередь analyzers и ждёт результат."""
    output = artifacts_dir / "archguard.json"
    async_result = celery_app.send_task(
        "analyzer.archguard",
        args=[str(repo_path), str(output), list(languages)],
        queue="analyzers",
    )
    async_result.get(timeout=timeout or settings.analyzer_timeout, disable_sync_subtasks=False)
    if not output.exists():
        raise RuntimeError("ArchGuard analyzer produced no output")
    return json.loads(output.read_text(encoding="utf-8"))


def dispatch_syntax_analyzer(
    repo_path: Path,
    artifacts_dir: Path,
    languages: list[str],
    timeout: int | None = None,
    run_id: str | None = None,
) -> dict:
    """Ставит Tree-sitter syntax-index в очередь analyzers и ждёт результат."""
    output = artifacts_dir / "syntax.json"
    async_result = celery_app.send_task(
        "analyzer.syntax",
        args=[str(repo_path), str(output), list(languages), run_id],
        queue="analyzers",
    )
    async_result.get(timeout=timeout or settings.analyzer_timeout, disable_sync_subtasks=False)
    if not output.exists():
        raise RuntimeError("syntax analyzer produced no output")
    return json.loads(output.read_text(encoding="utf-8"))


def dispatch_frontend_analyzer(
    repo_path: Path,
    artifacts_dir: Path,
    timeout: int | None = None,
    run_id: str | None = None,
) -> dict:
    """Ставит React frontend API index в очередь analyzers и ждёт результат."""
    output = artifacts_dir / "frontend.json"
    async_result = celery_app.send_task(
        "analyzer.frontend",
        args=[str(repo_path), str(output), run_id],
        queue="analyzers",
    )
    async_result.get(timeout=timeout or settings.analyzer_timeout, disable_sync_subtasks=False)
    if not output.exists():
        raise RuntimeError("frontend analyzer produced no output")
    return json.loads(output.read_text(encoding="utf-8"))
