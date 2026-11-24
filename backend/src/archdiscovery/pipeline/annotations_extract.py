import re
from pathlib import Path

IGNORED_DIRS = {".git", "node_modules", "dist", "build", "target", "__pycache__"}

JAVA_MAPPING_RE = re.compile(
    r"@(Get|Post|Put|Delete|Patch)Mapping\s*" r'(?:\(\s*(?:value\s*=\s*)?"([^"]*)"[^)]*\))?'
)
JAVA_REQUEST_BASE_RE = re.compile(r'@RequestMapping\(\s*(?:value\s*=\s*)?"([^"]*)"')
JAVA_PATH_RE = re.compile(r'@Path\(\s*"([^"]*)"\s*\)')
JAXRS_METHOD_RE = re.compile(r"@(GET|POST|PUT|DELETE|PATCH)\b")

CS_HTTP_RE = re.compile(
    r"\[Http(Get|Post|Put|Delete|Patch)(?:\(\s*\"([^\"]*)\"\s*\))?\]",
    re.IGNORECASE,
)

PY_FASTAPI_RE = re.compile(
    r"@(?:app|router)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
PY_FLASK_RE = re.compile(
    r"@(?:app|bp|blueprint)\.route\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?",
    re.IGNORECASE | re.DOTALL,
)

JS_ROUTE_RE = re.compile(
    r"\b(?:app|router)\.(get|post|put|delete|patch)\(\s*[\"'`]([^\"'`]+)[\"'`]",
    re.IGNORECASE,
)


def _java_endpoints(text: str) -> tuple[list[dict], str]:
    base_match = JAVA_PATH_RE.search(text) or JAVA_REQUEST_BASE_RE.search(text)
    base = base_match.group(1) if base_match else ""
    endpoints = [
        {"method": match.group(1).upper(), "path": base + (match.group(2) or "")}
        for match in JAVA_MAPPING_RE.finditer(text)
    ]
    if not endpoints:
        endpoints = [{"method": method, "path": base} for method in JAXRS_METHOD_RE.findall(text)]
    return endpoints, "java-rest"


def _cs_endpoints(text: str) -> tuple[list[dict], str]:
    endpoints = [
        {"method": match.group(1).upper(), "path": match.group(2) or ""}
        for match in CS_HTTP_RE.finditer(text)
    ]
    return endpoints, "aspnet"


def _py_endpoints(text: str) -> tuple[list[dict], str]:
    endpoints = [
        {"method": match.group(1).upper(), "path": match.group(2)}
        for match in PY_FASTAPI_RE.finditer(text)
    ]
    if endpoints:
        return endpoints, "fastapi"
    for match in PY_FLASK_RE.finditer(text):
        methods = match.group(2) or "GET"
        for method in re.findall(r"[A-Za-z]+", methods):
            endpoints.append({"method": method.upper(), "path": match.group(1)})
    return endpoints, "flask" if endpoints else "python"


def _js_endpoints(text: str) -> tuple[list[dict], str]:
    endpoints = [
        {"method": match.group(1).upper(), "path": match.group(2)}
        for match in JS_ROUTE_RE.finditer(text)
    ]
    return endpoints, "express"


def _endpoints_for(suffix: str, text: str) -> tuple[list[dict], str]:
    if suffix == ".java":
        return _java_endpoints(text)
    if suffix == ".cs":
        return _cs_endpoints(text)
    if suffix == ".py":
        return _py_endpoints(text)
    return _js_endpoints(text)


def extract_annotation_specs(repo_path: Path) -> list[dict]:
    specs: list[dict] = []
    suffixes = {".java", ".cs", ".py", ".js", ".jsx", ".ts", ".tsx"}

    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(repo_path).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:1_000_000]
        except OSError:
            continue

        endpoints, framework = _endpoints_for(path.suffix.lower(), text)
        if not endpoints:
            continue

        relative = str(path.relative_to(repo_path))
        specs.append(
            {
                "kind": "annotations",
                "name": relative,
                "spec": {
                    "file": relative,
                    "framework": framework,
                    "endpoints": endpoints,
                },
            }
        )
    return specs
