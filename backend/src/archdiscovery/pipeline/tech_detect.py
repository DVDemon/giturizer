import json
import re
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable
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

BASE_IMAGE_TECHNOLOGIES = [
    ("python", "Python", "language"),
    ("openjdk", "Java", "language"),
    ("eclipse-temurin", "Java", "language"),
    ("amazoncorretto", "Java", "language"),
    ("node", "Node.js", "runtime"),
    ("golang", "Go", "language"),
    ("dotnet", ".NET", "runtime"),
    ("aspnet", ".NET", "runtime"),
    ("rust", "Rust", "language"),
    ("ubuntu", "Ubuntu", "os"),
    ("debian", "Debian", "os"),
    ("alpine", "Alpine", "os"),
    ("userver", "userver", "framework"),
]

KNOWN_FRAMEWORKS = {"userver", "grpc", "boost", "drogon", "pistache", "crow"}

Adder = Callable[[str, str, str, "str | None"], None]


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


KIND_PRIORITY = {
    "language": 0,
    "framework": 1,
    "runtime": 1,
    "build": 2,
    "container": 3,
    "database": 4,
    "cache": 4,
    "orchestration": 5,
    "api": 6,
    "library": 7,
    "web-server": 8,
    "tool": 9,
    "ci": 9,
    "os": 10,
}


def _dedupe(technologies: list[Technology]) -> list[Technology]:
    """Один элемент на имя: оставляем более специфичный kind, версию сохраняем."""
    by_name: dict[str, Technology] = {}
    for tech in technologies:
        key = tech.name.lower()
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = tech
            continue
        keep, other = (
            (tech, existing)
            if KIND_PRIORITY.get(tech.kind, 50) < KIND_PRIORITY.get(existing.kind, 50)
            else (existing, tech)
        )
        by_name[key] = Technology(
            keep.name, keep.kind, keep.evidence, keep.version or other.version
        )
    return list(by_name.values())


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


def _tag_version(tag: str | None) -> str | None:
    """Версия из тега образа: 3.12-slim -> 3.12, 5.0.31-focal -> 5.0.31."""
    if not tag:
        return None
    candidate = tag.strip().lower().lstrip("v")
    if not re.search(r"\d", candidate):
        return None
    return re.split(r"[-+]", candidate, maxsplit=1)[0]


def _spec_version(spec: str | None) -> str | None:
    """Версия из ограничения зависимости: ^4.18.2 -> 4.18.2, >=1.0 -> 1.0."""
    if not spec:
        return None
    candidate = spec.strip().lstrip("<>=~^! ")
    match = re.search(r"[0-9][0-9A-Za-z.\-+]*", candidate)
    return match.group(0) if match else None


def _first_version(text: str) -> str | None:
    match = re.search(r"\d+(?:\.\d+)+", text)
    return match.group(0) if match else None


def _split_image(image: str) -> tuple[str, str | None]:
    reference = image.split("@", 1)[0]
    last_slash = reference.rfind("/")
    last_colon = reference.rfind(":")
    if last_colon > last_slash:
        return reference[:last_colon], _tag_version(reference[last_colon + 1 :])
    return reference, None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_package_json(path: Path, relative: str, add: Adder) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(document, dict):
        return
    for section in ("dependencies", "devDependencies"):
        dependencies = document.get(section)
        if isinstance(dependencies, dict):
            for name, spec in dependencies.items():
                add(name, "library", f"{relative}: {section}", _spec_version(str(spec)))
    engines = document.get("engines")
    if isinstance(engines, dict) and engines.get("node"):
        add("Node.js", "runtime", relative, _spec_version(str(engines["node"])))


def _parse_requirements(path: Path, relative: str, add: Adder) -> None:
    for line in _read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = re.match(r"([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(.*)", line)
        if not match:
            continue
        add(match.group(1), "library", relative, _spec_version(match.group(3)))


def _parse_pyproject(path: Path, relative: str, add: Adder) -> None:
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError):
        return
    project = document.get("project")
    if isinstance(project, dict):
        for dependency in project.get("dependencies") or []:
            match = re.match(r"([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(.*)", str(dependency))
            if match:
                add(match.group(1), "library", relative, _spec_version(match.group(3)))
        requires_python = project.get("requires-python")
        if requires_python:
            add("Python", "language", relative, _spec_version(str(requires_python)))
    poetry = (document.get("tool") or {}).get("poetry")
    if isinstance(poetry, dict):
        for name, spec in (poetry.get("dependencies") or {}).items():
            if name.lower() == "python":
                add("Python", "language", relative, _spec_version(str(spec)))
            else:
                add(name, "library", f"{relative}: poetry", _spec_version(str(spec)))


def _parse_pom(path: Path, relative: str, add: Adder) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return
    for element in root.iter():
        if _local_name(element.tag) == "java.version" and element.text:
            add("Java", "language", relative, _spec_version(element.text))
    for dependency in root.iter():
        if _local_name(dependency.tag) != "dependency":
            continue
        artifact = version = None
        for child in dependency:
            name = _local_name(child.tag)
            if name == "artifactId":
                artifact = child.text
            elif name == "version":
                version = child.text
        if artifact:
            add(artifact, "library", relative, _spec_version(version))
    for parent in root.iter():
        if _local_name(parent.tag) != "parent":
            continue
        artifact = version = None
        for child in parent:
            name = _local_name(child.tag)
            if name == "artifactId":
                artifact = child.text
            elif name == "version":
                version = child.text
        if artifact:
            add(artifact, "library", relative, _spec_version(version))


def _dotnet_version(framework: str) -> str | None:
    match = re.search(r"(\d+(?:\.\d+)?)", framework)
    return match.group(1) if match else None


def _parse_csproj(path: Path, relative: str, add: Adder) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return
    for element in root.iter():
        name = _local_name(element.tag)
        if name in {"TargetFramework", "TargetFrameworks"} and element.text:
            for framework in element.text.split(";"):
                version = _dotnet_version(framework)
                if version:
                    add(".NET", "runtime", relative, version)
        elif name == "PackageReference":
            package = element.get("Include")
            version = element.get("Version")
            if package:
                add(package, "library", relative, _spec_version(version))


GRADLE_DEPENDENCY = re.compile(
    r"(?:implementation|api|compileOnly|runtimeOnly|testImplementation)\s*\(?\s*"
    r"['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]"
)


def _parse_gradle(path: Path, relative: str, add: Adder) -> None:
    for group, artifact, version in GRADLE_DEPENDENCY.findall(_read_text(path)):
        add(f"{group}:{artifact}", "library", relative, _spec_version(version))


def _parse_go_mod(path: Path, relative: str, add: Adder) -> None:
    text = _read_text(path)
    go_match = re.search(r"^go\s+(\d+\.\d+(?:\.\d+)?)", text, re.MULTILINE)
    if go_match:
        add("Go", "language", relative, go_match.group(1))
    for match in re.finditer(
        r"^\s*(?:require\s+)?([\w.\-/]+)\s+v([0-9][\w.\-+]*)", text, re.MULTILINE
    ):
        module, version = match.group(1), match.group(2)
        if module != "go":
            add(module, "library", relative, version)


def detect_technologies(repo_path: Path) -> list[Technology]:
    techs: dict[tuple[str, str], Technology] = {}

    def add(name: str, kind: str, evidence: str, version: str | None = None) -> None:
        key = (kind, name.lower())
        if key in techs:
            existing = techs[key]
            if existing.version is None and version:
                techs[key] = Technology(existing.name, existing.kind, existing.evidence, version)
            return
        techs[key] = Technology(name=name, kind=kind, evidence=evidence, version=version)

    def set_version(name: str, version: str | None) -> None:
        if not version:
            return
        for key, tech in list(techs.items()):
            if tech.name.lower() == name.lower() and tech.version is None:
                techs[key] = Technology(tech.name, tech.kind, tech.evidence, version)

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
        build_match = build_files.get(path.name)
        if build_match:
            add(build_match[0], build_match[1], str(path.relative_to(repo_path)))

    for path in files:
        name = path.name.lower()
        relative = str(path.relative_to(repo_path))
        if name in {"dockerfile", "containerfile"} or name.startswith("dockerfile"):
            add("Docker", "container", relative)
            for from_match in re.finditer(
                r"^\s*FROM\s+([^\s]+)", _read_text(path), re.MULTILINE | re.IGNORECASE
            ):
                reference, version = _split_image(from_match.group(1))
                image_name = reference.rsplit("/", 1)[-1].lower()
                for marker, tech_name, kind in BASE_IMAGE_TECHNOLOGIES:
                    if image_name.startswith(marker):
                        if tech_name == "Ubuntu":
                            ubuntu = re.search(r"(\d{2}\.\d{2})", image_name)
                            version = ubuntu.group(1) if ubuntu else version
                        add(
                            tech_name,
                            kind,
                            f"{relative}: FROM {from_match.group(1)}",
                            version,
                        )
                        break
        elif name in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}:
            add("Docker Compose", "orchestration", relative)
            document = _load_yaml(path)
            services = document.get("services") if isinstance(document, dict) else None
            if isinstance(services, dict):
                for config in services.values():
                    if not isinstance(config, dict):
                        continue
                    image = str(config.get("image") or "")
                    image_name = image.rsplit("/", 1)[-1].lower()
                    for marker, tech_name, kind in IMAGE_TECHNOLOGIES:
                        if image_name.startswith(marker):
                            add(
                                tech_name,
                                kind,
                                f"{relative}: image {image}",
                                _split_image(image)[1],
                            )
                            break
        elif name == "chart.yaml":
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
    for cmake_match in re.finditer(
        r"find_package\(\s*([A-Za-z0-9_\-]+)(?:\s+([0-9][0-9A-Za-z.\-]*))?",
        cmake_text,
    ):
        package, raw_version = cmake_match.group(1), _spec_version(cmake_match.group(2))
        version = f">={raw_version}" if raw_version else None
        kind = "framework" if package.lower() in KNOWN_FRAMEWORKS else "library"
        add(package, kind, "CMake find_package", version)

    for match in re.finditer(
        r"cmake_minimum_required\(\s*VERSION\s+([0-9][0-9.\-]*)",
        cmake_text,
        re.IGNORECASE,
    ):
        minimum = _spec_version(match.group(1))
        if minimum:
            set_version("CMake", f">={minimum}")
        break

    for match in re.finditer(r"(?:CMAKE_CXX_STANDARD|CXX_STANDARD)\s+(\d+)", cmake_text):
        set_version("C++", match.group(1))
        break

    pending_versions: dict[str, str] = {}
    for path in files:
        if path.name != "CMakeLists.txt":
            continue
        text = _read_text(path)
        version_match = re.search(
            r"write_basic_package_version_file\([^)]*VERSION\s+([0-9][0-9A-Za-z.\-]*)",
            text,
            re.DOTALL,
        )
        if version_match:
            pending_versions[path.parent.name] = _spec_version(version_match.group(1)) or ""

        project_match = re.search(
            r"project\(\s*([\w\-]+)[^)]*?\bVERSION\s+([0-9][0-9A-Za-z.\-]*)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if project_match:
            pending_versions[project_match.group(1)] = _spec_version(project_match.group(2)) or ""

    sampled = [path for path in files if path.suffix.lower() in {".cpp", ".hpp", ".h"}][:200]
    for path in sampled:
        text = _read_text(path, limit=200_000)
        for marker, name in {
            "userver/": "userver",
            "grpc/": "gRPC",
            "boost/": "Boost",
            "jwt-cpp/": "jwt-cpp",
        }.items():
            if f"#include <{marker}" in text:
                add(name, "framework", str(path.relative_to(repo_path)))

    if any("jwt-cpp" in str(path) for path in files):
        add("jwt-cpp", "library", "vendored directory")

    for path in files:
        name = path.name.lower()
        relative = str(path.relative_to(repo_path))
        if name == "package.json":
            _parse_package_json(path, relative, add)
        elif name == ".python-version":
            version = _first_version(_read_text(path))
            if version:
                add("Python", "language", relative, version)
        elif name == ".nvmrc":
            version = _first_version(_read_text(path))
            if version:
                add("Node.js", "runtime", relative, version)
        elif name == "gradle-wrapper.properties":
            gradle_match = re.search(r"gradle-([\d.]+)-", _read_text(path))
            if gradle_match:
                add("Gradle", "build", relative, gradle_match.group(1))
        elif name == "maven-wrapper.properties":
            maven_match = re.search(r"maven-([\d.]+)-", _read_text(path))
            if maven_match:
                add("Maven", "build", relative, maven_match.group(1))
        elif name == ".java-version":
            version = _first_version(_read_text(path))
            if version:
                add("Java", "language", relative, version)
        elif name in {"rust-toolchain", "rust-toolchain.toml"}:
            version = _first_version(_read_text(path))
            if version:
                add("Rust", "language", relative, version)
        elif name in {"requirements.txt", "requirements-dev.txt"}:
            _parse_requirements(path, relative, add)
        elif name == "pyproject.toml":
            _parse_pyproject(path, relative, add)
        elif name == "pom.xml":
            _parse_pom(path, relative, add)
        elif name.endswith(".csproj"):
            _parse_csproj(path, relative, add)
        elif name in {"build.gradle", "build.gradle.kts"}:
            _parse_gradle(path, relative, add)
        elif name == "go.mod":
            _parse_go_mod(path, relative, add)

    for name, version in pending_versions.items():
        set_version(name, version or None)

    return sorted(_dedupe(list(techs.values())), key=lambda item: (item.kind, item.name.lower()))
