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

EXTERNAL_PATTERNS = (
    ("redis", re.compile(r"(?i)(redis|jedis|lettuce|redisson|ioredis)")),
    (
        "postgresql",
        re.compile(r"(?i)(postgres|psycopg|asyncpg|jdbc|jdbctemplate|r2dbc)"),
    ),
    ("s3", re.compile(r"(?i)(\bs3\b|boto3|aws-sdk/client-s3|minio)")),
    ("rabbitmq", re.compile(r"(?i)(rabbit|pika|amqp|rabbittemplate)")),
    ("kafka", re.compile(r"(?i)(kafka|kafkatemplate|confluent|kafkajs)")),
    ("mongodb", re.compile(r"(?i)(mongo|mongotemplate)")),
    ("elasticsearch", re.compile(r"(?i)(elasticsearch|opensearch)")),
    ("database", re.compile(r"(?i)(sqlalchemy|datasource|repository)")),
)

GENERIC_EXTERNAL_METHODS = {
    "execute": {"postgresql", "database"},
    "query": {"postgresql", "database"},
    "queryForObject": {"postgresql", "database"},
    "commit": {"postgresql", "database"},
    "add": {"postgresql", "database"},
    "refresh": {"postgresql", "database"},
    "flush": {"postgresql", "database"},
    "fetchone": {"postgresql", "database"},
    "fetchall": {"postgresql", "database"},
    "send": {"kafka"},
    "send_message": {"kafka"},
    "publish": {"rabbitmq", "kafka"},
    "basic_publish": {"rabbitmq"},
    "consume": {"kafka", "rabbitmq"},
    "get": {"redis"},
    "set": {"redis"},
    "hget": {"redis"},
    "hset": {"redis"},
    "put_object": {"s3"},
    "get_object": {"s3"},
}
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


def _targets_for(
    call: dict[str, Any],
    method: dict[str, Any],
    by_name: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    name = _last(call["callee"])
    candidates = by_name.get(name, [])
    if not candidates:
        return []
    receiver = _receiver(call["callee"])
    if receiver.startswith(("this.", "self.")):
        receiver = receiver.split(".", 1)[1]
    type_name = (method.get("types") or {}).get(receiver)
    if type_name:
        exact = [item for item in candidates if item.get("class") == type_name]
        # Тип известен, но его реализации нет в индексе (внешняя библиотека):
        # не подменяем вызов случайным одноимённым методом.
        return exact
    if receiver:
        exact = [item for item in candidates if item.get("class") == receiver]
        if exact:
            return exact
        if receiver in {"this", "self"}:
            return [item for item in candidates if item.get("class") == method.get("class")]
        return candidates if len(candidates) == 1 else []
    same_class = [item for item in candidates if item.get("class") == method.get("class")]
    return same_class or (candidates if len(candidates) == 1 else [])


def _external_kind(
    call: dict[str, Any],
    source_file: dict[str, Any],
    targets: list[dict[str, Any]],
    files_by_path: dict[str, dict[str, Any]],
) -> str | None:
    if _http_like(call):
        return "http"
    callee = call["callee"]
    # Импорты чужого файла не делают любой вызов внешним: учитываем
    # callee и имена target-классов (например, *Repository/*Client).
    target_text = " ".join(str(item.get("class") or "") for item in targets)
    haystack = f"{callee} {target_text}"
    for kind, pattern in EXTERNAL_PATTERNS:
        if pattern.search(haystack):
            return kind
    method = _last(callee)
    imports = " ".join(source_file.get("imports", []))
    allowed = GENERIC_EXTERNAL_METHODS.get(method)
    if allowed:
        for kind, pattern in EXTERNAL_PATTERNS:
            if kind in allowed and pattern.search(imports):
                return kind
    return None


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
    files_by_path = {item["file"]: item for item in files}
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
                targets = _targets_for(call, method, by_name)
                terminal_class = any(target.get("class") in client_classes for target in targets)
                external_kind = _external_kind(
                    call,
                    files_by_path.get(method["file"], {}),
                    targets,
                    files_by_path,
                )
                if external_kind is not None or terminal_class:
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
                                "targets": call.get("literals", [])[:5],
                                "kind": external_kind or "http",
                            },
                            "confidence": 0.75 if call.get("urls") else 0.65,
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
