"""P0 PoC: syntax index для API-потоков на Tree-sitter.

Не входит в production-пайплайн. Запуск:

    pip install -r requirements.txt
    python syntax_index.py fixtures
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

LANGUAGE_BY_SUFFIX = {
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".py": "python",
}

IMPORT_TYPES = {
    "preproc_include",
    "import_declaration",
    "import_statement",
    "import_from_statement",
}
CLASS_TYPES = {
    "class_specifier",
    "struct_specifier",
    "class_declaration",
    "interface_declaration",
    "class_definition",
}
FUNCTION_TYPES = {
    "function_definition",
    "function_declaration",
    "method_declaration",
    "method_definition",
}
CALL_TYPES = {"call_expression", "method_invocation", "call"}
ANNOTATION_TYPES = {"annotation", "marker_annotation", "decorator"}
STRING_TYPES = {"string_literal", "string", "raw_string_literal"}

URL_RE = re.compile(r"https?://[^\s\"'`]+|/api/v\d+/[^\s\"'`]+")
def walk(node: Node, source: bytes):
    yield node
    for child in node.children:
        yield from walk(child, source)


def text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def line(node: Node) -> int:
    return node.start_point.row + 1


def call_name(node: Node, source: bytes) -> str:
    for field in ("function", "name"):
        child = node.child_by_field_name(field)
        if child is not None:
            return text(child, source)
    return text(node, source).split("(", 1)[0].strip()


def symbol_name(node: Node, source: bytes) -> str:
    for field in ("name", "declarator"):
        child = node.child_by_field_name(field)
        if child is not None:
            raw = text(child, source).split("(", 1)[0].strip()
            match = re.search(r"([A-Za-z_]\w*)\s*$", raw)
            return match.group(1) if match else raw
    raw = text(node, source)
    match = re.search(r"([A-Za-z_]\w*)\s*\(", raw)
    return match.group(1) if match else raw.split("{", 1)[0].strip()


def string_values(node: Node, source: bytes) -> list[str]:
    return [text(item, source) for item in walk(node, source) if item.type in STRING_TYPES]


def annotation_value(raw: str) -> str:
    match = re.search(r"\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", raw)
    return match.group(1) if match else ""


def normalize_path(path: str) -> str:
    path = path.strip().strip('"\'')
    path = re.sub(r"\{[^}]+\}", "{}", path)
    path = re.sub(r":[A-Za-z_]\w*", "{}", path)
    return "/" + "/".join(part for part in path.split("/") if part)


def route_from_java(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    class_map: dict[str, str] = {}
    routes: list[dict[str, Any]] = []
    client_classes = {
        item["owner"]
        for item in nodes
        if item["kind"] == "annotation" and item["raw"].lower().startswith("@feignclient")
    }
    for item in nodes:
        if item["kind"] != "annotation":
            continue
        raw, owner, owner_kind = item["raw"], item["owner"], item["owner_kind"]
        if item.get("owner_class") in client_classes:
            continue
        lower = raw.lower()
        path = annotation_value(raw)
        if "requestmapping" in lower and owner_kind == "class":
            class_map[owner] = path
        method_match = re.search(r"@(Get|Post|Put|Delete|Patch)Mapping", raw, re.I)
        if method_match and owner_kind == "function":
            prefix = class_map.get(item["owner_class"] or "", "")
            path = f"{prefix}{path}"
            routes.append(
                {
                    "method": method_match.group(1).upper(),
                    "path": normalize_path(path),
                    "framework": "Spring",
                    "handler": owner,
                    "file": item["file"],
                    "line": item["line"],
                    "confidence": 0.9,
                }
            )
    return routes


def route_from_typescript(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    class_map: dict[str, str] = {}
    routes: list[dict[str, Any]] = []
    for item in nodes:
        if item["kind"] != "annotation":
            continue
        raw, owner, owner_kind = item["raw"], item["owner"], item["owner_kind"]
        if raw.lower().startswith("@controller") and owner_kind == "class":
            class_map[owner] = annotation_value(raw)
        match = re.match(r"@(Get|Post|Put|Delete|Patch)\(", raw, re.I)
        if match and owner_kind == "function":
            prefix = class_map.get(item["owner_class"] or "", "")
            routes.append(
                {
                    "method": match.group(1).upper(),
                    "path": normalize_path(f"{prefix}/{annotation_value(raw)}"),
                    "framework": "NestJS",
                    "handler": owner,
                    "file": item["file"],
                    "line": item["line"],
                    "confidence": 0.9,
                }
            )
    return routes


def route_from_python(path: Path, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    prefix_match = re.search(r"APIRouter\s*\(\s*prefix\s*=\s*[\"']([^\"']+)[\"']", source)
    prefix = prefix_match.group(1) if prefix_match else ""
    routes: list[dict[str, Any]] = []
    for item in nodes:
        if item["kind"] != "annotation":
            continue
        raw = item["raw"]
        match = re.match(r"@(\w+)\.(get|post|put|delete|patch)\(([^)]*)\)", raw, re.I)
        if match:
            routes.append(
                {
                    "method": match.group(2).upper(),
                    "path": normalize_path(f"{prefix}/{annotation_value(raw)}"),
                    "framework": "FastAPI",
                    "handler": item["owner"],
                    "file": item["file"],
                    "line": item["line"],
                    "confidence": 0.9,
                }
            )
    return routes


def analyze_file(path: Path, repo: Path) -> dict[str, Any]:
    language = LANGUAGE_BY_SUFFIX[path.suffix.lower()]
    parser = get_parser(language)
    source = path.read_bytes()
    tree = parser.parse(source)
    relative = str(path.relative_to(repo))

    imports: list[str] = []
    classes: list[str] = []
    functions: list[str] = []
    annotations: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    urls: list[dict[str, Any]] = []

    owners: list[dict[str, Any]] = []

    def visit(node: Node, current_class: str | None, current_function: str | None):
        if node.type in IMPORT_TYPES:
            imports.append(text(node, source))
        if node.type in CLASS_TYPES:
            current_class = symbol_name(node, source)
            classes.append(current_class)
            owners.append(
                {
                    "name": current_class,
                    "kind": "class",
                    "start": node.start_byte,
                    "end": node.end_byte,
                }
            )
        if node.type in FUNCTION_TYPES:
            current_function = symbol_name(node, source)
            functions.append(current_function)
            owners.append(
                {
                    "name": current_function,
                    "kind": "function",
                    "start": node.start_byte,
                    "end": node.end_byte,
                    "class": current_class,
                }
            )
        if node.type in CALL_TYPES:
            name = call_name(node, source)
            literal_urls = []
            for value in string_values(node, source):
                literal_urls.extend(URL_RE.findall(value))
            calls.append(
                {
                    "callee": name,
                    "line": line(node),
                    "caller": current_function or "",
                    "owner_class": current_class or "",
                    "urls": literal_urls,
                    "http_client_like": bool(HTTP_CLIENT_LIKE.match(name)),
                }
            )
        if node.type in ANNOTATION_TYPES:
            raw = text(node, source)
            annotations.append(
                {
                    "kind": "annotation",
                    "raw": raw,
                    "file": relative,
                    "line": line(node),
                    "start": node.start_byte,
                    "end": node.end_byte,
                    "parent": node.parent.type if node.parent else "",
                    "owner": "",
                    "owner_kind": "",
                    "owner_class": None,
                }
            )
        if node.type in STRING_TYPES:
            for value in URL_RE.findall(text(node, source)):
                urls.append({"value": value, "file": relative, "line": line(node)})

        for child in node.children:
            visit(child, current_class, current_function)

    visit(tree.root_node, None, None)

    for annotation in annotations:
        containing_functions = [
            owner
            for owner in owners
            if owner["kind"] == "function"
            and owner["start"] <= annotation["start"] < owner["end"]
        ]
        following_functions = [
            owner
            for owner in owners
            if owner["kind"] == "function" and owner["start"] >= annotation["end"]
        ]
        containing_classes = [
            owner
            for owner in owners
            if owner["kind"] == "class"
            and owner["start"] <= annotation["start"] < owner["end"]
        ]
        following_classes = [
            owner
            for owner in owners
            if owner["kind"] == "class" and owner["start"] >= annotation["end"]
        ]
        nearest_class = (
            min(following_classes, key=lambda item: item["start"])
            if following_classes
            else None
        )
        nearest_function = (
            min(following_functions, key=lambda item: item["start"])
            if following_functions
            else None
        )
        method_decorator = annotation.get("parent") in {
            "class_body",
            "decorated_definition",
        }
        if containing_functions:
            owner = min(
                containing_functions, key=lambda item: item["end"] - item["start"]
            )
        elif method_decorator and nearest_function is not None:
            owner = nearest_function
        elif containing_classes:
            owner = min(
                containing_classes, key=lambda item: item["end"] - item["start"]
            )
        elif nearest_class is not None and (
            nearest_function is None
            or nearest_class["start"] <= nearest_function["start"]
        ):
            owner = nearest_class
        elif nearest_function is not None:
            owner = nearest_function
        else:
            owner = None
        if owner is not None:
            annotation["owner"] = owner["name"]
            annotation["owner_kind"] = owner["kind"]
            annotation["owner_class"] = (
                owner.get("class")
                if owner["kind"] == "function"
                else owner["name"]
            )
        else:
            annotation["owner"] = annotation["owner"] or ""

    if language == "java":
        routes = route_from_java(annotations)
    elif language in {"typescript", "tsx"}:
        routes = route_from_typescript(annotations)
    elif language == "python":
        routes = route_from_python(path, annotations)
    else:
        routes = []

    return {
        "file": relative,
        "language": language,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "routes": routes,
        "owners": owners,
        "annotations": annotations,
        "calls": calls,
        "urls": urls,
    }


HTTP_CLIENT_LIKE = re.compile(
    r"(?i)(axios|fetch|httpx|requests|resttemplate|webclient|feign|okhttp|httpclient|client\.(post|get))"
)


def flow_candidates(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for file_entry in files:
        calls = file_entry["calls"]
        for route in file_entry["routes"]:
            matching = [
                call
                for call in calls
                if call["caller"] == route["handler"] and call["urls"]
            ]
            for call in matching:
                for url in call["urls"]:
                    candidates.append(
                        {
                            "input": {
                                "service": Path(route["file"]).stem,
                                "operation": f"{route['method']} {route['path']}",
                                "handler": {
                                    "file": route["file"],
                                    "line": route["line"],
                                    "symbol": route["handler"],
                                },
                            },
                            "output": {
                                "api": None,
                                "operation": None,
                                "url_template": url,
                                "client": {
                                    "file": file_entry["file"],
                                    "line": call["line"],
                                    "symbol": call["callee"],
                                },
                            },
                            "evidence": [
                                {
                                    "kind": "route",
                                    "file": route["file"],
                                    "line": route["line"],
                                    "value": route["framework"],
                                },
                                {
                                    "kind": "call",
                                    "file": file_entry["file"],
                                    "line": call["line"],
                                    "value": call["callee"],
                                },
                                {
                                    "kind": "url",
                                    "file": file_entry["file"],
                                    "line": call["line"],
                                    "value": url,
                                },
                            ],
                            "confidence": 0.6,
                            "status": "partial",
                        }
                    )
    return candidates


def build_index(repo: Path) -> dict[str, Any]:
    files = [
        analyze_file(path, repo)
        for path in sorted(repo.rglob("*"))
        if path.is_file() and path.suffix.lower() in LANGUAGE_BY_SUFFIX
    ]
    routes = [route for item in files for route in item["routes"]]
    calls = [
        {**call, "file": item["file"]}
        for item in files
        for call in item["calls"]
    ]
    outbound = [call for call in calls if call["urls"]]
    return {
        "files": files,
        "routes": routes,
        "calls": calls,
        "outbound_candidates": outbound,
        "api_flow_candidates": flow_candidates(files),
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures").resolve()
    result = build_index(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
