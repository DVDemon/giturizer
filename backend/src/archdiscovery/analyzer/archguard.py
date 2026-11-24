"""ArchGuard scanner: анализ Java/Kotlin/C#/TypeScript/Python/Golang."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SCANNER_JAR = Path(os.environ.get("ARCHGUARD_SCANNER_JAR", "/opt/archguard/scanner_cli.jar"))
ANALYSERS_DIR = Path(os.environ.get("ARCHGUARD_ANALYSERS_DIR", "/opt/archguard/analysers"))
ARCHGUARD_VERSION = os.environ.get("ARCHGUARD_VERSION", "2.3.0")

SUPPORTED_LANGUAGES = {"Java", "Kotlin", "TypeScript", "CSharp", "Golang", "Python"}
JAVA_FEATURES = ("apicalls", "datamap")
DATABASE_LIMIT_PER_LANGUAGE = 1000
FALLBACK_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "coverage"}
IMPORT_RE = re.compile(r'(?:from\s+|require\(\s*)["\']([^"\']+)["\']')


def _load_json(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def relative_path(value: str, repo_path: Path) -> str:
    """Приводит FilePath из ArchGuard к пути относительно корня репозитория."""
    path = str(value).replace("\\", "/")
    repo_abs = str(repo_path.resolve()).rstrip("/")
    if path.startswith(repo_abs + "/"):
        return path[len(repo_abs) + 1 :]
    candidate = path.lstrip("/")
    parts = candidate.split("/")
    for index in range(len(parts)):
        suffix = "/".join(parts[index:])
        if suffix and (repo_path / suffix).exists():
            return suffix
    return candidate


def module_key(relative: str) -> str:
    parts = relative.split("/")
    if parts and parts[0] == "services" and len(parts) > 1:
        return f"services/{parts[1]}"
    return parts[0] if len(parts) > 1 else "(root)"


def gitmodules(repo_path: Path) -> list[str]:
    path = repo_path / ".gitmodules"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return [match.strip() for match in re.findall(r"^\s*path\s*=\s*(.+)$", text, re.MULTILINE)]


def _fallback_scan(repo_path: Path, modules: list[str]) -> dict:
    """Лёгкий скан JS/TS для модулей, которые не покрыл ArchGuard (файлы + импорты)."""
    counts: dict[str, int] = {}
    files_total = 0
    imports_total = 0
    for module in modules:
        base = repo_path / module
        if not base.exists():
            continue
        count = 0
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(base)
            if any(part in SKIP_DIRS for part in relative.parts):
                continue
            if path.suffix.lower() not in FALLBACK_SUFFIXES:
                continue
            count += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
            except OSError:
                continue
            imports_total += sum(1 for value in IMPORT_RE.findall(text) if value.startswith("."))
        if count:
            counts[module] = count
            files_total += count
    return {"files": files_total, "imports": imports_total, "modules": counts}


def _prepare_workdir(workdir: Path) -> None:
    """Копирует предзагруженные анализаторы в dependencies/analysers (cwd сканера)."""
    target = workdir / "dependencies" / "analysers"
    target.mkdir(parents=True, exist_ok=True)
    for jar in ANALYSERS_DIR.glob("*.jar"):
        shutil.copy2(jar, target / jar.name)


def _run_scanner(
    repo_path: Path,
    language: str,
    workdir: Path,
    timeout: int,
) -> subprocess.CompletedProcess:
    command = [
        "java",
        "-Xmx4g",
        "-jar",
        str(SCANNER_JAR),
        "--type",
        "SOURCE_CODE",
        "--path",
        str(repo_path),
        "--language",
        language,
        "--output",
        "json",
    ]
    if language == "Java":
        for feature in JAVA_FEATURES:
            command.extend(["--features", feature])
    return subprocess.run(command, cwd=workdir, capture_output=True, text=True, timeout=timeout)


def analyze_archguard(
    repo_path: Path,
    output_path: Path,
    languages: list[str],
    timeout: int = 3600,
) -> dict:
    """Запускает ArchGuard по каждому языку; ошибки языков не валят остальные."""
    repo_path = repo_path.resolve()
    result: dict = {
        "tool": "archguard",
        "version": ARCHGUARD_VERSION,
        "languages": {},
        "summary": {},
        "apis": [],
        "databases": [],
        "fallback": {},
        "errors": [],
    }
    module_files: dict[str, int] = {}
    total_codes = total_apis = total_databases = 0

    for language in [item for item in languages if item in SUPPORTED_LANGUAGES]:
        workdir = Path(tempfile.mkdtemp(prefix=f"archguard-{language.lower()}-"))
        try:
            _prepare_workdir(workdir)
            proc = _run_scanner(repo_path, language, workdir, timeout)
            codes = _load_json(workdir / "0_codes.json")
            apis = _load_json(workdir / "0_apis.json")
            databases = _load_json(workdir / "0_databases.json")

            if proc.returncode != 0 or (not codes and not apis and not databases):
                message = (proc.stderr or proc.stdout or "scanner failed").strip()
                lines = [line.strip() for line in message.splitlines() if line.strip()]
                summary = next(
                    (line for line in reversed(lines) if "Exception" in line or "Error" in line),
                    lines[-1] if lines else "scanner failed",
                )
                result["errors"].append(
                    {
                        "language": language,
                        "summary": summary[:300],
                        "error": message[:4000],
                    }
                )
                continue

            modules: dict[str, int] = {}
            for item in codes:
                relative = relative_path(str(item.get("FilePath", "")), repo_path)
                key = module_key(relative)
                modules[key] = modules.get(key, 0) + 1
                module_files[key] = module_files.get(key, 0) + 1

            result["languages"][language] = {
                "codes": len(codes),
                "apis": len(apis),
                "databases": len(databases),
                "modules": dict(sorted(modules.items())),
            }
            total_codes += len(codes)
            total_apis += len(apis)
            total_databases += len(databases)
            result["apis"].extend(apis)
            result["databases"].extend(databases[:DATABASE_LIMIT_PER_LANGUAGE])
        except subprocess.TimeoutExpired:
            result["errors"].append({"language": language, "error": f"timeout after {timeout}s"})
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    submodules = gitmodules(repo_path)
    fallback = _fallback_scan(
        repo_path, [path for path in submodules if module_files.get(path, 0) == 0]
    )
    if fallback["files"]:
        result["fallback"] = fallback
    analyzed = [
        path
        for path in submodules
        if module_files.get(path, 0) > 0 or fallback["modules"].get(path, 0) > 0
    ]
    result["summary"] = {
        "codes": total_codes,
        "apis": total_apis,
        "databases": total_databases,
        "modules": dict(sorted(module_files.items())),
        "submodules": len(submodules),
        "submodules_analyzed": len(analyzed),
        "fallback_files": fallback["files"],
        "fallback_imports": fallback["imports"],
        "submodule_paths": submodules,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
