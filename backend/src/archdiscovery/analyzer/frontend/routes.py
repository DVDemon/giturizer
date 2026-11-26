"""Phase 2: React Router routes → page component → API calls."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

ROUTE_RE = re.compile(r"<Route\b([\s\S]*?)(?:/>|>\s*)", re.MULTILINE)
ADMIN_ROLE_RE = re.compile(r"withAdminRole\s*\(\s*\{([\s\S]*?)\}\s*\)", re.MULTILINE)
EXPORT_COMPONENT_RE = re.compile(r"export\s+(?:const|function|class)\s+([A-Z][A-Za-z0-9_]+)")
CONST_RE = re.compile(r"export\s+const\s+([A-Z][A-Z0-9_]+)\s*=\s*['\"]([^'\"]+)['\"]")
IMPORT_RE = re.compile(
    r"import\s+(?:\*\s+as\s+(\w+)|\{([^}]*)\}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
PAGE_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Page|View|Dashboard))\b")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _module_file(root: Path, from_file: Path, module: str) -> Path | None:
    if module.startswith("."):
        base = (from_file.parent / module).resolve()
    else:
        base = (root / "src" / module).resolve()
    candidates = [
        base,
        base.with_suffix(".ts"),
        base.with_suffix(".tsx"),
        base / "index.ts",
        base / "index.tsx",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _imports(root: Path, path: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for match in IMPORT_RE.finditer(_read(path)):
        namespace, named, default, module = match.groups()
        target = _module_file(root, path, module)
        if target is None:
            continue
        if namespace:
            result[namespace] = target
        elif default:
            result[default] = target
        elif named:
            for item in named.split(","):
                parts = [part.strip() for part in item.split(" as ")]
                if parts and parts[0]:
                    result[parts[-1]] = target
    return result


def _page_files(root: Path) -> dict[str, Path]:
    pages: dict[str, Path] = {}
    base = root / "src" / "pages"
    for path in sorted(base.rglob("*.tsx")):
        for name in EXPORT_COMPONENT_RE.findall(_read(path)):
            pages.setdefault(name, path)
    return pages


def _constants(root: Path, route_file: Path) -> tuple[dict[str, str], dict[str, str]]:
    consts: dict[str, str] = {}
    namespaces: dict[str, str] = {}
    for namespace, target in _imports(root, route_file).items():
        if target.name.startswith("const"):
            for name, value in CONST_RE.findall(_read(target)):
                consts[name] = value
            namespaces[namespace] = target.name
    # локальные константы route-файла
    for name, value in CONST_RE.findall(_read(route_file)):
        consts[name] = value
    return consts, namespaces


def _balanced(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        return "", start
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in {"`", "'", '"'}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
        index += 1
    return text[start + 1 :], len(text)


def _constant_path(expression: str, consts: dict[str, str]) -> str:
    value = expression.strip()
    value = re.sub(
        r"\$\{([A-Za-z_]\w*)\.([A-Z][A-Z0-9_]+)\}",
        lambda match: consts.get(match.group(2), match.group(0)),
        value,
    )
    value = re.sub(
        r"\b([A-Za-z_]\w*)\.([A-Z][A-Z0-9_]+)\b",
        lambda match: consts.get(match.group(2), match.group(0)),
        value,
    )
    value = value.strip("`")
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        value = value[1:-1]
    value = re.sub(r"\$\{[^}]+\}", "{}", value)
    return "/" + value.strip("/") if value.strip("/") else "/"


def _path(expression: str, consts: dict[str, str]) -> str:
    return _constant_path(expression, consts)


def _page_name(fragment: str) -> str | None:
    names = PAGE_RE.findall(fragment)
    return names[0] if names else None


def _route_path(block: str, consts: dict[str, str], offset: int = 0) -> str | None:
    match = re.search(r"path\s*=\s*", block)
    if not match:
        return None
    pos = match.end()
    if pos < len(block) and block[pos] == "{":
        expr, _ = _balanced(block, pos)
    else:
        expr_match = re.match(r"([`'\"])(.*?)\1", block[pos:], re.DOTALL)
        expr = expr_match.group(2) if expr_match else ""
    if not expr:
        return None
    return _constant_path(expr, consts)


def _extract_routes(root: Path, route_file: Path) -> list[dict[str, Any]]:
    source = _read(route_file)
    consts, _ = _constants(root, route_file)
    routes: list[dict[str, Any]] = []
    positions = [match.start() for match in re.finditer(r"<Route\b", source)]
    for pos in positions:
        block = source[
            pos : (
                source.find("</Routes>", pos)
                if source.find("</Routes>", pos) != -1
                else len(source)
            )
        ]
        # ограничиваем блок следующим Route, чтобы не взять чужой element
        next_route = source.find("<Route\b", pos + 1)
        if next_route != -1:
            block = source[pos:next_route]
        path_value = _route_path(block, consts)
        if path_value is None:
            continue
        element_pos = block.find("element")
        fragment = block[element_pos:] if element_pos != -1 else block
        page = _page_name(fragment)
        if not page:
            continue
        routes.append(
            {
                "path": path_value,
                "component": page,
                "file": str(route_file.relative_to(root)),
                "line": source[:pos].count("\n") + 1,
            }
        )
    for match in re.finditer(r"withAdminRole\s*\(", source):
        brace = source.find("{", match.end())
        if brace == -1:
            continue
        block, _ = _balanced(source, brace)
        path_match = re.search(r"path\s*:\s*", block)
        if not path_match:
            continue
        expr_start = path_match.end()
        if expr_start < len(block) and block[expr_start] == "`":
            end_quote = block.find("`", expr_start + 1)
            expr = block[expr_start : end_quote + 1] if end_quote != -1 else block[expr_start:]
        else:
            comma = block.find(",", expr_start)
            expr = block[expr_start : comma if comma != -1 else len(block)]
        page = _page_name(block)
        if not page:
            continue
        routes.append(
            {
                "path": _constant_path(expr, consts),
                "component": page,
                "file": str(route_file.relative_to(root)),
                "line": source[: match.start()].count("\n") + 1,
            }
        )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for route in routes:
        unique.setdefault((route["path"], route["component"]), route)
    return list(unique.values())


def _import_originals(root: Path, path: Path) -> dict[str, tuple[Path, str | None]]:
    result: dict[str, tuple[Path, str | None]] = {}
    for match in IMPORT_RE.finditer(_read(path)):
        namespace, named, default, module = match.groups()
        target = _module_file(root, path, module)
        if target is None:
            continue
        if namespace:
            result[namespace] = (target, None)
        elif default:
            result[default] = (target, None)
        elif named:
            for item in named.split(","):
                parts = [part.strip() for part in item.split(" as ")]
                if not parts or not parts[0]:
                    continue
                result[parts[-1]] = (target, parts[0])
    return result


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


def _all_calls(path: Path) -> list[dict[str, Any]]:
    parser = get_parser("tsx" if path.suffix.lower() == ".tsx" else "typescript")
    source = path.read_bytes()
    tree = parser.parse(source)
    result: list[dict[str, Any]] = []

    def visit(node: Node) -> None:
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            if function is not None:
                result.append(
                    {
                        "callee": _text(function, source),
                        "function": _enclosing_function(node, source),
                        "line": node.start_point.row + 1,
                    }
                )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return result


def _collect_component_calls(
    root: Path,
    page_file: Path,
    component: str,
    calls_by_file: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    all_cache: dict[Path, list[dict[str, Any]]] = {}
    api_by_function: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for relative, calls in calls_by_file.items():
        for call in calls:
            api_by_function.setdefault((relative, call.get("function", "")), []).append(call)

    def calls_for(path: Path) -> list[dict[str, Any]]:
        if path not in all_cache:
            all_cache[path] = _all_calls(path)
        return all_cache[path]

    def collect(
        path: Path, function: str, depth: int, visited: set[tuple[Path, str]]
    ) -> list[dict[str, Any]]:
        key = (path, function)
        if depth > 4 or key in visited:
            return []
        visited.add(key)
        relative = str(path.relative_to(root))
        result = list(api_by_function.get((relative, function), []))
        imports = _import_originals(root, path)
        local_functions = {call["function"] for call in calls_for(path) if call["function"]}
        for call in calls_for(path):
            if call["function"] != function:
                continue
            callee = call["callee"].split(".")[-1]
            if callee in imports:
                target, original = imports[callee]
                target_function = original or callee
                # Если функция не распознана как API-функция, не тянем весь модуль.
                result.extend(collect(target, target_function, depth + 1, visited))
            elif callee in local_functions:
                result.extend(collect(path, callee, depth + 1, visited))
        return result

    result = collect(page_file, component, 0, set())
    if not result:
        # Fallback: прямые API-вызовы страницы.
        result = list(calls_by_file.get(str(page_file.relative_to(root)), []))
    return result


def build_ui_flows(
    root: Path,
    calls_by_file: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    router_candidates = [
        path for path in (root / "src" / "router").rglob("*") if path.suffix in {".ts", ".tsx"}
    ]
    router_file = next(
        (path for path in router_candidates if "index" in path.name),
        router_candidates[0] if router_candidates else None,
    )
    if router_file is None:
        return [], []
    routes = _extract_routes(root, router_file)
    pages = _page_files(root)
    flows: list[dict[str, Any]] = []
    for route in routes:
        page_file = pages.get(route["component"])
        calls: list[dict[str, Any]] = []
        if page_file is not None:
            calls = _collect_component_calls(root, page_file, route["component"], calls_by_file)
            route["component_file"] = str(page_file.relative_to(root))
        unique: dict[tuple, dict[str, Any]] = {}
        for call in calls:
            key = (call["method"], call["normalized_path"], call["service"])
            unique.setdefault(key, call)
        flows.append(
            {
                "route": route["path"],
                "component": route["component"],
                "component_file": route.get("component_file"),
                "calls": list(unique.values()),
            }
        )
    return routes, flows
