"""Детекция endpoint → handler для Java Spring, NestJS/Express, FastAPI/Flask."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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
    handlers.sort(key=lambda item: (item["handler"]["file"], item["handler"]["line"], item["path"]))
    return handlers
