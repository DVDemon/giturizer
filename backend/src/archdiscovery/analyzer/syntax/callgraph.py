"""P2: call graph handler → outbound HTTP/gRPC/GraphQL-кандидат."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any

HTTP_CALL_MARKERS = (
    "axios",
    "httpx",
    "requests",
    "aiohttp",
    "resttemplate",
    "webclient",
    "okhttp",
    "httpclient",
    "httpservice",
    "superagent",
)
MAX_DEPTH = 6


def _last(callee: str) -> str:
    return callee.strip().split(".")[-1].split("(")[0].strip()


def _receiver(callee: str) -> str:
    parts = callee.strip().split(".")
    return ".".join(parts[:-1]).split("(")[0].strip()


def _http_like(call: dict[str, Any]) -> bool:
    callee = call["callee"].lower()
    if call.get("http_client_like"):
        return True
    if re.search(r"(?i)(?:^|\.)fetch(?:\s*\(|$)", callee):
        return True
    if re.search(r"(?i)(?:^|\.)got(?:\s*\(|$)", callee):
        return True
    return any(marker in callee for marker in HTTP_CALL_MARKERS)


def _client_classes(files: list[dict[str, Any]]) -> set[str]:
    classes: set[str] = set()
    for file_entry in files:
        for annotation in file_entry["annotations"]:
            raw = annotation["raw"].lower()
            if annotation["owner_kind"] != "class":
                continue
            if raw.startswith("@feignclient") or raw.startswith("@httpclient"):
                classes.add(annotation["owner"])
    return classes


def _method_key(method: dict[str, Any]) -> tuple[str, str | None, str]:
    return (method["file"], method.get("class"), method["name"])


def _same_scope(
    method: dict[str, Any], receiver: str | None, by_name: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    candidates = by_name.get(method["name"], [])
    if not candidates:
        return []
    if receiver:
        exact = [item for item in candidates if item.get("class") == receiver]
        if exact:
            return exact
        if receiver in {"this", "self"}:
            same_class = [item for item in candidates if item.get("class") == method.get("class")]
            return same_class
        # Неизвестный receiver: не размножаем граф по всем одноимённым методам.
        return candidates if len(candidates) == 1 else []
    same_class = [item for item in candidates if item.get("class") == method.get("class")]
    return same_class or (candidates if len(candidates) == 1 else [])


def build_outbound_calls(
    files: list[dict[str, Any]], handlers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    methods = [method for item in files for method in item["methods"]]
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for method in methods:
        by_name[method["name"]].append(method)

    calls_by_owner: dict[tuple[str, str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for file_entry in files:
        for call in file_entry["calls"]:
            owner = (file_entry["file"], call.get("owner_class"), call["caller"])
            calls_by_owner[owner].append(call)

    client_classes = _client_classes(files)
    outbound: list[dict[str, Any]] = []

    for handler in handlers:
        handler_symbol = handler["handler"]["symbol"]
        handler_class = handler["handler"].get("class")
        handler_file = handler["handler"]["file"]
        start = next(
            (
                method
                for method in methods
                if method["file"] == handler_file
                and method["name"] == handler_symbol
                and (handler_class is None or method.get("class") == handler_class)
            ),
            None,
        )
        if start is None:
            continue

        queue: deque[tuple[dict[str, Any], list[dict[str, Any]]]] = deque([(start, [start])])
        visited_methods = {_method_key(start)}
        seen_outbound: set[tuple[Any, ...]] = set()
        while queue and len(seen_outbound) < 50:
            method, path = queue.popleft()
            if len(path) > MAX_DEPTH:
                continue
            for call in calls_by_owner.get(_method_key(method), []):
                targets = _same_scope(
                    {
                        "name": _last(call["callee"]),
                        "class": method.get("class"),
                    },
                    _receiver(call["callee"]),
                    by_name,
                )
                terminal_class = any(target.get("class") in client_classes for target in targets)
                if _http_like(call) or terminal_class:
                    outbound_key: tuple[Any, ...] = (
                        call["file"],
                        call["line"],
                        call["callee"],
                        path[-1]["file"],
                        path[-1]["line"],
                    )
                    if outbound_key in seen_outbound:
                        continue
                    seen_outbound.add(outbound_key)
                    outbound.append(
                        {
                            "input": {
                                "operation": f"{handler['method']} {handler['path']}",
                                "handler": handler["handler"],
                            },
                            "path": [
                                {
                                    "symbol": item["name"],
                                    "class": item.get("class"),
                                    "file": item["file"],
                                    "line": item["line"],
                                }
                                for item in path
                            ],
                            "output": {
                                "callee": call["callee"],
                                "file": call["file"],
                                "line": call["line"],
                                "urls": call.get("urls", []),
                                "kind": "http",
                            },
                            "confidence": 0.75 if call.get("urls") else 0.6,
                            "status": "partial",
                        }
                    )
                    continue
                for target in targets:
                    key = _method_key(target)
                    if key in visited_methods:
                        continue
                    visited_methods.add(key)
                    queue.append((target, [*path, target]))

    # Дедупликация одинаковых путей.
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in outbound:
        unique_key: tuple[Any, ...] = (
            item["input"]["operation"],
            tuple((step["file"], step["line"], step["symbol"]) for step in item["path"]),
            item["output"]["file"],
            item["output"]["line"],
        )
        unique.setdefault(unique_key, item)
    return list(unique.values())
