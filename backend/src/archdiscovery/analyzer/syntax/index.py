"""Общий syntax-index: imports, классы, функции, аннотации и вызовы."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

LANGUAGE_BY_SUFFIX = {
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".py": "python",
}
IMPORT_TYPES = {
    "import_declaration",
    "import_statement",
    "import_from_statement",
}
CLASS_TYPES = {
    "class_declaration",
    "interface_declaration",
    "class_definition",
}
FUNCTION_TYPES = {
    "function_declaration",
    "method_declaration",
    "method_definition",
    "function_definition",
}
CALL_TYPES = {"call_expression", "method_invocation", "call"}
ANNOTATION_TYPES = {"annotation", "marker_annotation", "decorator"}
STRING_TYPES = {"string_literal", "string", "raw_string_literal"}
URL_RE = re.compile(r"https?://[^\s\"'`]+|/api/v\d+/[^\s\"'`]+")
HTTP_CLIENT_RE = re.compile(
    r"(?i)(axios|fetch|httpx|requests|resttemplate|webclient|feign|okhttp|httpclient)"
)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _line(node: Node) -> int:
    return node.start_point.row + 1


def _symbol_name(node: Node, source: bytes) -> str:
    for field in ("name", "declarator"):
        child = node.child_by_field_name(field)
        if child is not None:
            raw = _text(child, source).split("(", 1)[0].strip()
            match = re.search(r"([A-Za-z_]\w*)\s*$", raw)
            return match.group(1) if match else raw
    raw = _text(node, source)
    match = re.search(r"([A-Za-z_]\w*)\s*\(", raw)
    return match.group(1) if match else raw.split("{", 1)[0].strip()


def _call_name(node: Node, source: bytes) -> str:
    for field in ("function", "name"):
        child = node.child_by_field_name(field)
        if child is not None:
            return _text(child, source)
    return _text(node, source).split("(", 1)[0].strip()


def _strings(node: Node, source: bytes) -> list[str]:
    return [_text(item, source) for item in _walk(node, source) if item.type in STRING_TYPES]


def _walk(node: Node, source: bytes):
    yield node
    for child in node.children:
        yield from _walk(child, source)


def owner_for_annotation(
    annotation: dict[str, Any], owners: list[dict[str, Any]]
) -> dict[str, Any] | None:
    containing_functions = [
        owner
        for owner in owners
        if owner["kind"] == "function" and owner["start"] <= annotation["start"] < owner["end"]
    ]
    containing_classes = [
        owner
        for owner in owners
        if owner["kind"] == "class" and owner["start"] <= annotation["start"] < owner["end"]
    ]
    following_functions = [
        owner
        for owner in owners
        if owner["kind"] == "function" and owner["start"] >= annotation["end"]
    ]
    following_classes = [
        owner
        for owner in owners
        if owner["kind"] == "class" and owner["start"] >= annotation["end"]
    ]
    method_decorator = annotation.get("parent") in {
        "class_body",
        "decorated_definition",
    }
    if containing_functions:
        return min(containing_functions, key=lambda item: item["end"] - item["start"])
    if method_decorator and following_functions:
        return min(following_functions, key=lambda item: item["start"])
    if containing_classes:
        return min(containing_classes, key=lambda item: item["end"] - item["start"])
    if following_classes and (
        not following_functions
        or min(item["start"] for item in following_classes)
        <= min(item["start"] for item in following_functions)
    ):
        return min(following_classes, key=lambda item: item["start"])
    if following_functions:
        return min(following_functions, key=lambda item: item["start"])
    return None


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
    owners: list[dict[str, Any]] = []

    def visit(node: Node, current_class: str | None, current_function: str | None) -> None:
        if node.type in IMPORT_TYPES:
            imports.append(_text(node, source))
        if node.type in CLASS_TYPES:
            current_class = _symbol_name(node, source)
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
            current_function = _symbol_name(node, source)
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
            urls: list[str] = []
            for value in _strings(node, source):
                urls.extend(URL_RE.findall(value))
            name = _call_name(node, source)
            calls.append(
                {
                    "callee": name,
                    "line": _line(node),
                    "caller": current_function or "",
                    "owner_class": current_class or "",
                    "urls": urls,
                    "http_client_like": bool(HTTP_CLIENT_RE.search(name)),
                }
            )
        if node.type in ANNOTATION_TYPES:
            annotations.append(
                {
                    "raw": _text(node, source),
                    "file": relative,
                    "line": _line(node),
                    "start": node.start_byte,
                    "end": node.end_byte,
                    "parent": node.parent.type if node.parent else "",
                    "owner": "",
                    "owner_kind": "",
                    "owner_class": None,
                }
            )
        for child in node.children:
            visit(child, current_class, current_function)

    visit(tree.root_node, None, None)
    for annotation in annotations:
        owner = owner_for_annotation(annotation, owners)
        if owner is not None:
            annotation["owner"] = owner["name"]
            annotation["owner_kind"] = owner["kind"]
            annotation["owner_class"] = (
                owner.get("class") if owner["kind"] == "function" else owner["name"]
            )

    return {
        "file": relative,
        "language": language,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "annotations": annotations,
        "calls": calls,
    }
