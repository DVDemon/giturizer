import re
from pathlib import Path

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
SERVICE_RE = re.compile(r"\bservice\s+(\w+)\s*\{")
RPC_RE = re.compile(
    r"\brpc\s+(\w+)\s*\(\s*(stream\s+)?([\w.]+)\s*\)\s*" r"returns\s*\(\s*(stream\s+)?([\w.]+)\s*\)"
)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _block(text: str, start: int) -> str:
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    return text[start : index - 1]


def _extract_services(text: str) -> list[dict]:
    services: list[dict] = []
    for match in SERVICE_RE.finditer(text):
        body = _block(text, match.end())
        rpcs = [
            {
                "name": rpc.group(1),
                "request": rpc.group(3),
                "response": rpc.group(5),
                "client_streaming": bool(rpc.group(2)),
                "server_streaming": bool(rpc.group(4)),
            }
            for rpc in RPC_RE.finditer(body)
        ]
        services.append({"name": match.group(1), "rpcs": rpcs})
    return services


def extract_grpc_specs(repo_path: Path) -> list[dict]:
    specs: list[dict] = []
    for path in repo_path.rglob("*.proto"):
        if not path.is_file() or ".git" in path.relative_to(repo_path).parts:
            continue
        try:
            text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        services = _extract_services(text)
        if not services:
            continue
        package = PACKAGE_RE.search(text)
        specs.append(
            {
                "kind": "grpc",
                "name": str(path.relative_to(repo_path)),
                "spec": {
                    "file": str(path.relative_to(repo_path)),
                    "package": package.group(1) if package else None,
                    "services": services,
                },
            }
        )
    return specs
