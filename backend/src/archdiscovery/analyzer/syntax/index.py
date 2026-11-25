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
TYPE_ANNOTATION_RE = re.compile(r"\b([A-Za-z_]\w*)\s*:\s*([A-Z][A-Za-z0-9_.]*)")
JAVA_TYPE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9_<>?, ]*?)\s+([a-z_]\w*)\s*(?=[=;,\)]|$)", re.MULTILINE
)
HTTP_CLIENT_RE = re.compile(
    r"(?i)(?:axios|httpx|requests|aiohttp|resttemplate|webclient|feign|okhttp|httpclient|httpservice|superagent)"
    r"(?:\.|\()|(?:^|\.)fetch(?:\(|$)|(?:^|\.)got(?:\(|$)"
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
    if node.type == "method_invocation":
        name = node.child_by_field_name("name")
        receiver = node.child_by_field_name("object")
        if name is not None and receiver is not None:
            if receiver.type in {"identifier", "field_access"}:
                return f"{_text(receiver, source)}.{_text(name, source)}"
            return _text(name, source)
        if name is not None:
            return _text(name, source)
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


def _infer_types(text: str) -> dict[str, str]:
    types: dict[str, str] = {}
    for name, type_name in TYPE_ANNOTATION_RE.findall(text):
        types[name] = type_name.split("<", 1)[0].split(".")[-1]
    for type_name, name in JAVA_TYPE_RE.findall(text):
        base = type_name.split("<", 1)[0].strip().split(".")[-1]
        if base not in {"public", "private", "protected", "final", "static"}:
            types.setdefault(name, base)
    return types


def analyze_file(path: Path, repo: Path) -> dict[str, Any]:
    language = LANGUAGE_BY_SUFFIX[path.suffix.lower()]
    parser = get_parser(language)
    source = path.read_bytes()
    tree = parser.parse(source)
    relative = str(path.relative_to(repo))

    imports: list[str] = []
    classes: list[str] = []
    functions: list[str] = []
    methods: list[dict[str, Any]] = []
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
            methods.append(
                {
                    "name": current_function,
                    "class": current_class,
                    "file": relative,
                    "line": _line(node),
                    "start": node.start_byte,
                    "end": node.end_byte,
                }
            )
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
            strings = _strings(node, source)
            urls: list[str] = []
            for value in strings:
                urls.extend(URL_RE.findall(value))
            literals = [value.strip("'\"") for value in strings]
            name = _call_name(node, source)
            calls.append(
                {
                    "callee": name,
                    "file": relative,
                    "line": _line(node),
                    "caller": current_function or "",
                    "owner_class": current_class,
                    "urls": urls,
                    "literals": literals,
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

    class_types: dict[str, dict[str, str]] = {}
    for owner in owners:
        if owner["kind"] != "class":
            continue
        class_text = source[owner["start"] : owner["end"]].decode("utf-8", "replace")
        class_types[owner["name"]] = _infer_types(class_text)
    for method in methods:
        method_text = source[method["start"] : method["end"]].decode("utf-8", "replace")
        types = dict(class_types.get(method.get("class") or "", {}))
        types.update(_infer_types(method_text))
        method["types"] = types

    return {
        "file": relative,
        "language": language,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "annotations": annotations,
        "methods": methods,
        "calls": calls,
    }
