"""P1: production syntax-index и endpoint→handler для Java/TS/Python."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import tree_sitter

from archdiscovery.analyzer.syntax.callgraph import build_outbound_calls
from archdiscovery.analyzer.syntax.index import LANGUAGE_BY_SUFFIX, analyze_file
from archdiscovery.analyzer.syntax.routes import build_handlers

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "target",
    "build",
    "dist",
    "generated",
    "test",
    "tests",
    "fixtures",
}
SUPPORTED_LANGUAGES = {"java", "typescript", "python"}


def _iter_files(repo_path: Path, languages: set[str]) -> Iterable[Path]:
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in LANGUAGE_BY_SUFFIX:
            continue
        language = LANGUAGE_BY_SUFFIX[path.suffix.lower()]
        if language not in languages:
            continue
        parts = path.relative_to(repo_path).parts
        if any(part in EXCLUDED_DIRS for part in parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        yield path


def analyze_syntax(
    repo_path: Path,
    output_path: Path,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    requested = set(languages or SUPPORTED_LANGUAGES) & SUPPORTED_LANGUAGES
    files: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in sorted(_iter_files(repo_path, requested)):
        try:
            files.append(analyze_file(path, repo_path))
        except Exception as exc:  # noqa: BLE001 - один файл не валит анализ
            errors.append(
                {
                    "file": str(path.relative_to(repo_path)),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    handlers = build_handlers(files, repo_path)
    outbound_calls = build_outbound_calls(files, handlers)
    result = {
        "tool": "tree-sitter",
        "version": tree_sitter.__version__,
        "languages": sorted({item["language"] for item in files}),
        "handlers": handlers,
        "outbound_calls": outbound_calls,
        "stats": {
            "files": len(files),
            "handlers": len(handlers),
            "outbound_calls": len(outbound_calls),
            "languages": sorted({item["language"] for item in files}),
        },
        "errors": errors,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
