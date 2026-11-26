"""Синтетические API-спеки из syntax handlers (C++/POCO и др.)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import RunArtifact


def load_syntax_handlers(session: Session, run_id: Any) -> list[dict[str, Any]]:
    artifact = session.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id == run_id,
            RunArtifact.kind == "syntax",
        )
    ).first()
    if artifact is None or not isinstance(artifact.content, dict):
        return []
    return [
        handler
        for handler in artifact.content.get("handlers", [])
        if isinstance(handler, dict) and handler.get("path")
    ]


def _existing_endpoints(specs: list[dict[str, Any]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for spec in specs:
        raw = spec.get("spec") or {}
        if spec.get("kind") == "annotations":
            for endpoint in raw.get("endpoints") or []:
                if isinstance(endpoint, dict) and endpoint.get("path"):
                    result.add(
                        (
                            str(endpoint.get("method") or "GET").upper(),
                            str(endpoint["path"]),
                        )
                    )
        elif spec.get("kind") == "openapi":
            for path, item in (raw.get("paths") or {}).items():
                if isinstance(item, dict):
                    for method in ("get", "post", "put", "delete", "patch"):
                        if method in item:
                            result.add((method.upper(), path))
    return result


def syntax_specs(
    handlers: list[dict[str, Any]],
    service: str,
    existing_specs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    existing = _existing_endpoints(existing_specs or [])
    by_file: dict[str, dict[str, Any]] = {}
    for handler in handlers:
        method = str(handler.get("method") or "").upper()
        path = str(handler.get("path") or "")
        if not method or not path or (method, path) in existing:
            continue
        source = handler.get("handler") or {}
        file = str(source.get("file") or "syntax")
        framework = str(handler.get("framework") or "syntax")
        entry = by_file.setdefault(
            file,
            {
                "kind": "annotations",
                "name": file,
                "spec": {
                    "file": file,
                    "framework": framework,
                    "service": service,
                    "endpoints": [],
                },
            },
        )
        endpoints = entry["spec"]["endpoints"]
        item = {"method": method, "path": path}
        if item not in endpoints:
            endpoints.append(item)
    return list(by_file.values())


def merge_into_report(
    report: dict[str, Any],
    handlers: list[dict[str, Any]],
    service: str,
) -> dict[str, Any]:
    existing_ops = {
        (entry.get("service"), method.get("operation"))
        for entry in report.get("api", [])
        for method in entry.get("methods", [])
    }
    for handler in handlers:
        operation = f"{handler.get('method', '').upper()} {handler.get('path', '')}".strip()
        if not operation or (service, operation) in existing_ops:
            continue
        entry = next(
            (item for item in report.setdefault("api", []) if item.get("service") == service),
            None,
        )
        if entry is None:
            entry = {"service": service, "methods": []}
            report["api"].append(entry)
        entry["methods"].append(
            {
                "operation": operation,
                "description": f"Найдено syntax-index: {handler.get('framework', 'syntax')}",
                "technology": str(handler.get("framework") or "syntax"),
            }
        )
        existing_ops.add((service, operation))
    return report
