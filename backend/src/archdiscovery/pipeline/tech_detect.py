import re
from dataclasses import dataclass
from pathlib import Path

import yaml

IGNORED_DIRS = {
    ".git",
    ".github",
    "node_modules",
    "target",
    "build",
    "dist",
    ".venv",
    "venv",
    "__pycache__",
}

CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".h"}
PY_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
JAVA_EXTENSIONS = {".java"}
CS_EXTENSIONS = {".cs"}

IMAGE_TECHNOLOGIES = [
    ("postgres", "PostgreSQL", "database"),
    ("mongo", "MongoDB", "database"),
    ("redis", "Redis", "cache"),
    ("valkey", "Valkey", "cache"),
    ("nginx", "nginx", "web-server"),
    ("swagger-ui", "Swagger UI", "tool"),
]

KNOWN_FRAMEWORKS = {"userver", "grpc", "boost", "drogon", "pistache", "crow"}


@dataclass(frozen=True)
class Technology:
    name: str
    kind: str
    evidence: str
    version: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "evidence": self.evidence,
            "version": self.version,
        }


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _read_text(path: Path, limit: int = 500_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _load_yaml(path: Path):
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None


def detect_technologies(repo_path: Path) -> list[Technology]:
    techs: dict[tuple[str, str], Technology] = {}

    def add(name: str, kind: str, evidence: str, version: str | None = None) -> None:
        key = (kind, name.lower())
        if key not in techs:
            techs[key] = Technology(name=name, kind=kind, evidence=evidence, version=version)

    files = list(_iter_files(repo_path))
    ext_counts: dict[str, int] = {}
    for path in files:
        suffix = path.suffix.lower()
        ext_counts[suffix] = ext_counts.get(suffix, 0) + 1

    cpp_count = sum(ext_counts.get(ext, 0) for ext in CPP_EXTENSIONS)
    if cpp_count:
        add("C++", "language", f"{cpp_count} files")
    if ext_counts.get(".py"):
        add("Python", "language", f"{ext_counts['.py']} files")
    if ext_counts.get(".java"):
        add("Java", "language", f"{ext_counts['.java']} files")
    if ext_counts.get(".cs"):
        add("C#", "language", f"{ext_counts['.cs']} files")
    js_count = sum(ext_counts.get(ext, 0) for ext in JS_EXTENSIONS)
    if js_count:
        add("JavaScript/TypeScript", "language", f"{js_count} files")

    proto_count = ext_counts.get(".proto", 0)
    if proto_count:
        add("Protocol Buffers", "api", f"{proto_count} files")
    gql_count = sum(ext_counts.get(ext, 0) for ext in (".graphql", ".gql"))
    if gql_count:
        add("GraphQL", "api", f"{gql_count} files")

    build_files = {
        "CMakeLists.txt": ("CMake", "build"),
        "CMakePresets.json": ("CMake presets", "build"),
        "package.json": ("npm", "build"),
        "pom.xml": ("Maven", "build"),
        "build.gradle": ("Gradle", "build"),
        "build.gradle.kts": ("Gradle", "build"),
        "pyproject.toml": ("Python packaging", "build"),
        "requirements.txt": ("pip", "build"),
        "go.mod": ("Go modules", "build"),
    }
    for path in files:
        match = build_files.get(path.name)
        if match:
            add(match[0], match[1], str(path.relative_to(repo_path)))

    for path in files:
        name = path.name.lower()
        relative = str(path.relative_to(repo_path))
        if name in {"dockerfile", "containerfile"} or name.startswith("dockerfile"):
            add("Docker", "container", relative)
        elif name in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}:
            add("Docker Compose", "orchestration", relative)
            document = _load_yaml(path)
            services = document.get("services") if isinstance(document, dict) else None
            if isinstance(services, dict):
                for config in services.values():
                    if not isinstance(config, dict):
                        continue
                    image = str(config.get("image") or "").lower()
                    for marker, tech_name, kind in IMAGE_TECHNOLOGIES:
                        if image.startswith(marker):
                            add(tech_name, kind, f"{relative}: image {image}")
        elif name in {"chart.yaml"}:
            add("Helm", "orchestration", relative)
        elif name == ".gitlab-ci.yml":
            add("GitLab CI", "ci", relative)
        elif name.endswith((".yaml", ".yml")):
            document = _load_yaml(path)
            if isinstance(document, dict) and "apiVersion" in document and "kind" in document:
                kind = str(document.get("kind"))
                if kind in {"Deployment", "StatefulSet", "DaemonSet", "Service", "Ingress"}:
                    add("Kubernetes", "orchestration", relative)
                if kind in {"Application", "AppProject"}:
                    add("ArgoCD", "orchestration", relative)
        elif name.startswith(("openapi", "swagger")) and path.suffix.lower() in {
            ".yaml",
            ".yml",
            ".json",
        }:
            add("OpenAPI", "api", relative)

    cmake_text = "\n".join(_read_text(path) for path in files if path.name == "CMakeLists.txt")
    for package in set(re.findall(r"find_package\(\s*([A-Za-z0-9_\-]+)", cmake_text)):
        kind = "framework" if package.lower() in KNOWN_FRAMEWORKS else "library"
        add(package, kind, "CMake find_package")

    sampled = [path for path in files if path.suffix.lower() in {".cpp", ".hpp", ".h"}][:200]
    for path in sampled:
        text = _read_text(path, limit=200_000)
        for marker in ("userver/", "grpc/", "boost/", "jwt-cpp/"):
            if f"#include <{marker}" in text:
                name = {
                    "userver/": "userver",
                    "grpc/": "gRPC",
                    "boost/": "Boost",
                    "jwt-cpp/": "jwt-cpp",
                }[marker]
                add(name, "framework", str(path.relative_to(repo_path)))

    if any("jwt-cpp" in str(path) for path in files):
        add("jwt-cpp", "library", "vendored directory")

    return sorted(techs.values(), key=lambda item: (item.kind, item.name.lower()))
