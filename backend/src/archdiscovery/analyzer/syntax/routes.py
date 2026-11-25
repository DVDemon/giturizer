"""Детекция endpoint → handler для Java Spring, NestJS/Express, FastAPI/Flask."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

HTTP_DECORATOR_RE = re.compile(r"@(?:[A-Za-z_]\w*\.)?(get|post|put|delete|patch)\b", re.IGNORECASE)
JAVA_MAPPING_RE = re.compile(r"@(Get|Post|Put|Delete|Patch)Mapping\b", re.IGNORECASE)
JAXRS_MAPPING_RE = re.compile(r"@(GET|POST|PUT|DELETE|PATCH)\b")
JAXRS_PATH_RE = re.compile(r"@Path\s*\(\s*[\"']([^\"']+)[\"']")
ARG_RE = re.compile(r"\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']")


def _arg(raw: str) -> str:
    match = ARG_RE.search(raw)
    return match.group(1) if match else ""


def _normalize_path(prefix: str, path: str) -> str:
    combined = "/".join(part.strip("/") for part in (prefix, path) if part and part.strip("/"))
    combined = re.sub(r"\{[^}]+\}", "{}", combined)
    combined = re.sub(r":[A-Za-z_]\w*", "{}", combined)
    return "/" + combined if combined else "/"


def _handler(
    *,
    method: str,
    path: str,
    annotation: dict[str, Any],
    framework: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "method": method.upper(),
        "path": path,
        "handler": {
            "file": annotation["file"],
            "line": annotation["line"],
            "symbol": annotation["owner"],
            "class": annotation.get("owner_class"),
            "language": "",
            "framework": framework,
        },
        "source": {"file": annotation["file"], "line": annotation["line"]},
        "framework": framework,
        "confidence": confidence,
    }


def java_routes(file_entry: dict[str, Any]) -> list[dict[str, Any]]:
    annotations = file_entry["annotations"]
    controllers = {
        item["owner"]
        for item in annotations
        if item["owner_kind"] == "class"
        and item["raw"].lower() in {"@restcontroller", "@controller"}
    }
    feign_clients = {
        item["owner"]
        for item in annotations
        if item["owner_kind"] == "class" and item["raw"].lower().startswith("@feignclient")
    }
    prefixes: dict[str, str] = {}
    for item in annotations:
        if item["owner_kind"] == "class" and "requestmapping" in item["raw"].lower():
            prefixes[item["owner"]] = _arg(item["raw"])

    routes: list[dict[str, Any]] = []
    for item in annotations:
        owner_class = item.get("owner_class")
        if owner_class in feign_clients:
            continue
        if item["owner_kind"] != "function" or owner_class not in controllers:
            continue
        match = JAVA_MAPPING_RE.search(item["raw"])
        if match:
            route = _handler(
                method=match.group(1),
                path=_normalize_path(prefixes.get(owner_class, ""), _arg(item["raw"])),
                annotation=item,
                framework="Spring",
                confidence=0.95,
            )
            route["handler"]["language"] = "java"
            routes.append(route)

    # JAX-RS: @Path на классе + @GET/@POST на методе.
    jaxrs_prefixes = {}
    for item in annotations:
        if item["owner_kind"] != "class":
            continue
        match = JAXRS_PATH_RE.search(item["raw"])
        if match:
            jaxrs_prefixes[item["owner"]] = match.group(1)
    for item in annotations:
        if item["owner_kind"] != "function":
            continue
        match = JAXRS_MAPPING_RE.search(item["raw"])
        if not match:
            continue
        prefix = jaxrs_prefixes.get(item.get("owner_class") or "", "")
        route = _handler(
            method=match.group(1),
            path=_normalize_path(prefix, ""),
            annotation=item,
            framework="JAX-RS",
            confidence=0.85,
        )
        route["handler"]["language"] = "java"
        routes.append(route)
    return routes


def typescript_routes(file_entry: dict[str, Any]) -> list[dict[str, Any]]:
    annotations = file_entry["annotations"]
    controllers = {
        item["owner"]
        for item in annotations
        if item["owner_kind"] == "class" and item["raw"].lower().startswith("@controller")
    }
    prefixes = {
        item["owner"]: _arg(item["raw"])
        for item in annotations
        if item["owner_kind"] == "class" and item["raw"].lower().startswith("@controller")
    }
    routes: list[dict[str, Any]] = []
    for item in annotations:
        if item["owner_kind"] != "function":
            continue
        owner_class = item.get("owner_class")
        if owner_class not in controllers:
            continue
        match = HTTP_DECORATOR_RE.search(item["raw"])
        if not match:
            continue
        route = _handler(
            method=match.group(1),
            path=_normalize_path(prefixes.get(owner_class, ""), _arg(item["raw"])),
            annotation=item,
            framework="NestJS",
            confidence=0.9,
        )
        route["handler"]["language"] = "typescript"
        routes.append(route)

    # Express/Fastify: router.get("/path", handler), app.post(...).
    for call in file_entry["calls"]:
        match = re.match(r"(?:app|router|fastify)\.(get|post|put|delete|patch)$", call["callee"])
        if not match or not call["urls"]:
            continue
        routes.append(
            {
                "method": match.group(1).upper(),
                "path": _normalize_path("", call["urls"][0]),
                "handler": {
                    "file": file_entry["file"],
                    "line": call["line"],
                    "symbol": call["caller"] or "anonymous",
                    "class": call.get("owner_class"),
                    "language": "typescript",
                    "framework": "Express",
                },
                "source": {"file": file_entry["file"], "line": call["line"]},
                "framework": "Express",
                "confidence": 0.6,
            }
        )
    return routes


def python_routes(file_entry: dict[str, Any], repo_path: Path) -> list[dict[str, Any]]:
    annotations = file_entry["annotations"]
    source_path = repo_path / file_entry["file"]
    try:
        source = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        source = ""
    prefix_match = re.search(r"APIRouter\s*\(\s*prefix\s*=\s*[\"']([^\"']+)[\"']", source)
    prefix = prefix_match.group(1) if prefix_match else ""
    routes: list[dict[str, Any]] = []
    for item in annotations:
        if item["owner_kind"] != "function":
            continue
        raw = item["raw"]
        match = re.search(
            r"@(?:[A-Za-z_]\w*\.)?(get|post|put|delete|patch)\s*\(", raw, re.IGNORECASE
        )
        if match:
            routes.append(
                _handler(
                    method=match.group(1),
                    path=_normalize_path(prefix, _arg(raw)),
                    annotation=item,
                    framework="FastAPI",
                    confidence=0.9,
                )
            )
            routes[-1]["handler"]["language"] = "python"
            continue
        route_match = re.search(r"@(?:[A-Za-z_]\w*\.)?route\s*\(", raw)
        if route_match:
            methods = re.findall(r"[\"'](GET|POST|PUT|DELETE|PATCH)[\"']", raw)
            routes.append(
                _handler(
                    method=methods[0] if methods else "GET",
                    path=_normalize_path(prefix, _arg(raw)),
                    annotation=item,
                    framework="Flask",
                    confidence=0.8,
                )
            )
            routes[-1]["handler"]["language"] = "python"
    return routes


def build_handlers(files: list[dict[str, Any]], repo_path: Path) -> list[dict[str, Any]]:
    handlers: list[dict[str, Any]] = []
    for file_entry in files:
        language = file_entry["language"]
        if language == "java":
            handlers.extend(java_routes(file_entry))
        elif language in {"typescript", "tsx"}:
            handlers.extend(typescript_routes(file_entry))
        elif language == "python":
            handlers.extend(python_routes(file_entry, repo_path))
        elif language == "cpp":
            handlers.extend(cpp_routes(file_entry, repo_path))
    handlers.sort(key=lambda item: (item["handler"]["file"], item["handler"]["line"], item["path"]))
    return handlers


CPP_ROUTE_CALL_IGNORES = {
    "jsonObject",
    "jsonArray",
    "sendJson",
    "sendError",
    "sendNoContent",
    "response.set",
}


def _cpp_text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _cpp_calls(node: Node, source: bytes) -> list[str]:
    calls: list[str] = []
    for child in node.children:
        if child.type == "call_expression":
            function = child.child_by_field_name("function")
            if function is not None:
                calls.append(_cpp_text(function, source).strip())
        calls.extend(_cpp_calls(child, source))
    return calls


def _cpp_if_parts(node: Node) -> tuple[Node | None, Node | None]:
    condition = node.child_by_field_name("condition")
    if condition is None:
        condition = next(
            (child for child in node.children if child.type == "condition_clause"),
            None,
        )
    body = node.child_by_field_name("consequence") or node.child_by_field_name("body")
    if body is None:
        body = next(
            (
                child
                for child in node.children
                if child.type not in {"if", "condition_clause", "else"}
            ),
            None,
        )
    return condition, body


def _cpp_function_name(node: Node, source: bytes) -> str:
    text = _cpp_text(node, source)
    head = text.split("{", 1)[0]
    matches = re.findall(r"([A-Za-z_]\w*)\s*\(", head)
    return matches[-1] if matches else ""


def cpp_routes(file_entry: dict[str, Any], repo_path: Path) -> list[dict[str, Any]]:
    """POCO HTTPRequestHandler + dispatch(method, segments)."""
    path = repo_path / file_entry["file"]
    try:
        source = path.read_bytes()
    except OSError:
        return []
    tree = get_parser("cpp").parse(source)
    routes: list[dict[str, Any]] = []

    def visit(node: Node) -> None:
        if node.type == "class_specifier":
            class_text = _cpp_text(node, source)
            head = class_text.split("{", 1)[0]
            if re.search(r"\bHTTPRequestHandler\b(?!Factory)", head):
                name_node = node.child_by_field_name("name")
                class_name = (
                    _cpp_text(name_node, source) if name_node is not None else "HTTPHandler"
                )

                def walk_functions(parent: Node) -> None:
                    for child in parent.children:
                        if child.type == "function_definition":
                            method = _cpp_function_name(child, source)
                            if method in {"dispatch", "handleRequest"}:
                                for statement in child.children:
                                    _collect_if(statement, class_name)
                        else:
                            walk_functions(child)

                walk_functions(node)
        for child in node.children:
            visit(child)

    def _collect_if(node: Node, class_name: str) -> None:
        if node.type == "if_statement":
            condition, body = _cpp_if_parts(node)
            if condition is not None and body is not None:
                cond = _cpp_text(condition, source)
                method_match = re.search(
                    r'(?i)\bmethod\s*==\s*"(GET|POST|PUT|DELETE|PATCH)"',
                    cond,
                )
                method = method_match.group(1).upper() if method_match else ""
                if method and ("segments." in cond or "segments[" in cond):
                    calls = [
                        name
                        for name in _cpp_calls(body, source)
                        if name not in CPP_ROUTE_CALL_IGNORES
                        and "." not in name
                        and "->" not in name
                    ]
                    if calls:
                        handler = calls[0]
                        if "segments.empty()" in cond:
                            path_value = "/"
                        else:
                            size_match = re.search(r"segments\.size\(\)\s*==\s*(\d+)", cond)
                            literals = {
                                int(index): value
                                for index, value in re.findall(
                                    r'segments\[(\d+)\]\s*==\s*"([^"]+)"', cond
                                )
                            }
                            size = (
                                int(size_match.group(1))
                                if size_match
                                else (max(literals) + 1 if literals else 0)
                            )
                            parts = [literals.get(index, "{}") for index in range(size)]
                            path_value = "/" + "/".join(parts) if parts else "/"
                        routes.append(
                            {
                                "method": method,
                                "path": path_value,
                                "handler": {
                                    "file": file_entry["file"],
                                    "line": node.start_point.row + 1,
                                    "symbol": handler,
                                    "class": class_name,
                                    "language": "cpp",
                                    "framework": "POCO",
                                },
                                "source": {
                                    "file": file_entry["file"],
                                    "line": node.start_point.row + 1,
                                },
                                "framework": "POCO",
                                "confidence": 0.8,
                            }
                        )
        for child in node.children:
            _collect_if(child, class_name)

    visit(tree.root_node)
    unique: dict[tuple, dict[str, Any]] = {}
    for route in routes:
        key = (route["method"], route["path"], route["handler"]["symbol"])
        unique.setdefault(key, route)
    return list(unique.values())
