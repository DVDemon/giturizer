"""Phase 1: API index для React-фронтенда через Tree-sitter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from archdiscovery.analyzer.frontend.routes import build_ui_flows

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "target",
    "tests",
    "test",
    "__tests__",
    "mocks",
}
SKIP_FILE_RE = re.compile(r"(mock|fixture|stories|test|spec)\.(ts|tsx|js|jsx)$", re.I)
CALL_RE = re.compile(r"^(Api|axios|http|api)\.(get|post|put|patch|delete)$", re.I)
URL_PROP_RE = re.compile(r"""url\s*:\s*(`[^`]*`|'[^']*'|"[^"]*")""", re.DOTALL)
STRING_RE = re.compile(r"^[`'\"].*[`'\"]$", re.DOTALL)

SERVICE_BY_GATEWAY = {
    "auth": "fdm-auth",
    "user": "fdm-auth",
    "capability": "capability-backend",
    "product": "fdm-products",
    "cx": "cx-backend",
    "techradar": "techradar-backend",
    "document": "document-service",
    "project": "project-backend",
    "ff": "ff-manager",
    "ai-chat": "ai-chat-service",
    "notify": "fdm-notifications-management",
    "camunda-process": "fdm-bpm",
    "solution-checker": "solution-checker",
    "staging-service": "staging-service",
    "dashboard-service": "dashboard-service",
    "obs-dashboard": "dashboard",
    "sequence-backend": "sequence-backend",
    "staging-sequence": "staging-sequence",
    "ambassador": "ambassador",
    "graph-validator": "graph-validator",
}
PREFIX_SERVICE = {
    "/product/api": "fdm-products",
    "/arch-graph/api": "architect-graph-service",
    "/capability/api": "capability-backend",
    "/cx/api": "cx-backend",
    "/ai-chat/api": "ai-chat-service",
    "/staging-service/api": "staging-service",
    "/solution-checker/api": "solution-checker",
    "/user/api": "fdm-auth",
    "/ff/api": "ff-manager",
    "/project/api": "project-backend",
    "/structurizr-backend": "structurizr-backend",
    "/dashboard-service": "dashboard-service",
    "/obs-dashboard": "dashboard",
    "/sequence-backend": "sequence-backend",
    "/staging-sequence": "staging-sequence",
    "/ambassador": "ambassador",
    "/graph-validator": "graph-validator",
    "/camunda": "fdm-bpm",
}


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _enclosing_function(node: Node, source: bytes) -> str:
    current = node.parent
    while current is not None:
        if current.type in {"function_declaration", "method_definition"}:
            name = current.child_by_field_name("name")
            if name is not None:
                return _text(name, source)
        if current.type == "variable_declarator":
            name = current.child_by_field_name("name")
            value = current.child_by_field_name("value")
            if (
                name is not None
                and value is not None
                and value.type
                in {
                    "arrow_function",
                    "function_expression",
                }
            ):
                return _text(name, source)
        current = current.parent
    return ""


def _frontend_roots(repo: Path) -> list[Path]:
    roots: list[Path] = []
    for package in repo.rglob("package.json"):
        if any(part in EXCLUDED_DIRS for part in package.relative_to(repo).parts):
            continue
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "react" in deps or "react-dom" in deps:
            roots.append(package.parent)
    return roots


def _prefixes(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, value in re.findall(r"const\s+(PREFIX_[A-Z0-9_]+)\s*=\s*[\"']([^\"']+)", text):
            values[name] = value
        for name, true_name, false_name in re.findall(
            r"export\s+const\s+(GATEWAY_[A-Z0-9_]+)\s*=\s*IS_DEV\s*\?\s*"
            r"([A-Za-z0-9_]+)\s*:\s*([A-Za-z0-9_]+)",
            text,
        ):
            values[name] = values.get(false_name, values.get(true_name, ""))
    return values


def _resolve_url(raw: str, prefixes: dict[str, str]) -> str:
    value = raw.strip()
    if value[:1] in {"`", "'", '"'}:
        value = value[1:-1]
    value = re.sub(
        r"\$\{([A-Za-z0-9_]+)\}",
        lambda match: (prefixes[match.group(1)] if match.group(1) in prefixes else match.group(0)),
        value,
    )
    value = re.sub(r"\$\{[^}]+\}", "{}", value)
    value = value.split("?", 1)[0]
    value = re.sub(r"/{2,}", "/", value)
    return value.rstrip("/") or "/"


def _service_and_path(url: str) -> tuple[str, str]:
    gateway = re.match(r"^/api-gateway/([^/]+)(/.*)?$", url)
    if gateway:
        service = gateway.group(1)
        rest = gateway.group(2) or "/"
        mapped = SERVICE_BY_GATEWAY.get(service, service)
        if service in {
            "auth",
            "user",
            "capability",
            "product",
            "techradar",
            "document",
            "project",
            "ff",
        }:
            path = "/api" + rest
        else:
            path = rest
        return mapped, path
    for prefix, service in PREFIX_SERVICE.items():
        if url == prefix or url.startswith(prefix + "/"):
            rest = url[len(prefix) :] or "/"
            if rest == "/" or rest.startswith("/api/"):
                return service, rest
            if prefix == "/cx/api":
                return service, "/api/cx" + rest
            if prefix == "/camunda":
                return service, rest
            return service, "/api" + rest
    return "unknown", url


def _url_from_args(arg_text: str) -> str:
    match = URL_PROP_RE.search(arg_text)
    return match.group(1) if match else ""


def _calls(path: Path, root: Path, prefixes: dict[str, str]) -> list[dict[str, Any]]:
    suffix = ".tsx" if path.suffix.lower() == ".tsx" else ".ts"
    parser = get_parser("tsx" if suffix == ".tsx" else "typescript")
    source = path.read_bytes()
    tree = parser.parse(source)
    relative = str(path.relative_to(root))
    result: list[dict[str, Any]] = []

    def visit(node: Node) -> None:
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            args = node.child_by_field_name("arguments")
            callee = _text(function, source) if function is not None else ""
            match = CALL_RE.match(callee)
            method = ""
            source_kind = callee
            if match:
                method = match.group(2).upper()
            elif callee == "fetch":
                method = "GET"
                source_kind = "fetch"
            elif "." in callee and callee.rsplit(".", 1)[0] in {"axios", "http", "api"}:
                method = callee.rsplit(".", 1)[1].upper()
            if method and args is not None and args.named_child_count > 0:
                first = args.named_children[0]
                if first.type in {"string", "template_string"}:
                    raw = _text(first, source)
                elif first.type in {"object", "object_pattern"}:
                    raw = _url_from_args(_text(first, source))
                else:
                    raw = ""
                if raw:
                    url = _resolve_url(raw, prefixes)
                    service, service_path = _service_and_path(url)
                    result.append(
                        {
                            "file": relative,
                            "line": node.start_point.row + 1,
                            "method": method,
                            "url_template": url,
                            "normalized_path": service_path,
                            "service": service,
                            "source": source_kind,
                            "function": _enclosing_function(node, source),
                            "confidence": 0.85,
                        }
                    )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return result


def _files(root: Path) -> list[Path]:
    base = root / "src" if (root / "src").is_dir() else root
    result: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".ts", ".tsx"}:
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if SKIP_FILE_RE.search(path.name) or path.stat().st_size > 1_500_000:
            continue
        result.append(path)
    return sorted(result)


def analyze_frontend(
    repo_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    frontends: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for root in _frontend_roots(repo_path):
        prefixes = _prefixes(root)
        files = _files(root)
        frontends.append(
            {"root": str(root.relative_to(repo_path)), "name": root.name, "framework": "react"}
        )
        for path in files:
            try:
                calls.extend(_calls(path, root, prefixes))
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "file": str(path.relative_to(repo_path)),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    # дедупликация запросов
    unique: dict[tuple, dict[str, Any]] = {}
    calls_by_file: dict[str, list[dict[str, Any]]] = {}
    for call in calls:
        key = (call["file"], call["line"], call["method"], call["url_template"])
        unique.setdefault(key, call)
        calls_by_file.setdefault(call["file"], []).append(call)
    calls = list(unique.values())
    routes: list[dict[str, Any]] = []
    ui_flows: list[dict[str, Any]] = []
    for frontend in frontends:
        root = repo_path / frontend["root"]
        frontend_routes, frontend_flows = build_ui_flows(root, calls_by_file)
        routes.extend(frontend_routes)
        ui_flows.extend(frontend_flows)
    result = {
        "tool": "tree-sitter",
        "frontends": frontends,
        "api_calls": calls,
        "routes": routes,
        "ui_flows": ui_flows,
        "stats": {
            "frontends": len(frontends),
            "files": sum(len(_files(Path(repo_path) / frontend["root"])) for frontend in frontends),
            "api_calls": len(calls),
            "routes": len(routes),
            "ui_flows": len(ui_flows),
        },
        "errors": errors,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
