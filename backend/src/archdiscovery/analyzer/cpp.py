import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CPP_SUFFIXES = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".h", ".ixx"}
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*(?:<([^>]+)>|"([^"]+)")', re.MULTILINE)
CLASS_RE = re.compile(r"\b(?:class|struct)\s+([A-Za-z_]\w*)")
COMPOUND_RE = re.compile(r"<compound\b([^>]*)>\s*<name>([^<]+)</name>")

FRAMEWORK_MARKERS = {
    "userver/": "userver",
    "grpc/": "gRPC",
    "boost/": "Boost",
    "jwt-cpp/": "jwt-cpp",
}


def _iter_cpp_files(repo_path: Path):
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.relative_to(repo_path).parts:
            continue
        if path.suffix.lower() in CPP_SUFFIXES:
            yield path


def _parse_doxygen_index(text: str) -> list[str]:
    classes: list[str] = []
    for attributes, name in COMPOUND_RE.findall(text):
        if 'kind="class"' in attributes or 'kind="struct"' in attributes:
            classes.append(name.strip())
    return sorted(set(classes))


def _doxygen_classes(repo_path: Path) -> dict:
    if shutil.which("doxygen") is None:
        return {"available": False, "classes": []}

    workdir = Path(tempfile.mkdtemp(prefix="archdiscovery-doxygen-"))
    try:
        doxyfile = workdir / "Doxyfile"
        doxyfile.write_text(
            "\n".join(
                [
                    "PROJECT_NAME = analysis",
                    f"INPUT = {repo_path}",
                    "RECURSIVE = YES",
                    "GENERATE_HTML = NO",
                    "GENERATE_XML = YES",
                    "XML_OUTPUT = xml",
                    "XML_PROGRAMLISTING = NO",
                    "EXTRACT_ALL = YES",
                    "HAVE_DOT = NO",
                    "QUIET = YES",
                    "EXCLUDE_PATTERNS = */.git/*",
                ]
            ),
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["doxygen", str(doxyfile)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            return {"available": True, "classes": [], "error": proc.stderr[-500:]}
        index = workdir / "xml" / "index.xml"
        if not index.exists():
            return {"available": True, "classes": []}
        text = index.read_text(encoding="utf-8", errors="replace")
        return {"available": True, "classes": _parse_doxygen_index(text)}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": True, "classes": [], "error": str(exc)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def analyze_cpp(repo_path: Path, output_path: Path) -> dict:
    files = sorted(_iter_cpp_files(repo_path))
    by_relative = {str(path.relative_to(repo_path)): path for path in files}
    by_name: dict[str, Path] = {}
    for path in files:
        by_name.setdefault(path.name, path)

    file_entries: list[dict] = []
    edges: list[dict] = []
    frameworks: set[str] = set()
    system_includes = 0
    resolved_root = repo_path.resolve()

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:2_000_000]
        except OSError:
            continue
        relative = str(path.relative_to(repo_path))
        includes: list[dict] = []

        for system_include, local_include in INCLUDE_RE.findall(text):
            if system_include:
                system_includes += 1
                includes.append({"target": system_include, "local": False})
                for marker, name in FRAMEWORK_MARKERS.items():
                    if system_include.startswith(marker):
                        frameworks.add(name)
                continue

            resolved: str | None = None
            candidate = (path.parent / local_include).resolve()
            try:
                candidate_relative = str(candidate.relative_to(resolved_root))
                if candidate_relative in by_relative:
                    resolved = candidate_relative
            except ValueError:
                resolved = None
            if resolved is None and local_include in by_name:
                resolved = str(by_name[local_include].relative_to(repo_path))

            includes.append({"target": local_include, "local": True, "resolved": resolved})
            if resolved:
                edges.append({"from": relative, "to": resolved, "kind": "include"})

        file_entries.append(
            {
                "path": relative,
                "classes": sorted(set(CLASS_RE.findall(text))),
                "includes": includes,
            }
        )

    cmake_text = ""
    for cmake in repo_path.rglob("CMakeLists.txt"):
        if ".git" in cmake.parts:
            continue
        try:
            cmake_text += cmake.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    cmake_packages = sorted(set(re.findall(r"find_package\(\s*([A-Za-z0-9_\-]+)", cmake_text)))
    for package in cmake_packages:
        if package.lower() in {"userver", "grpc", "boost"}:
            frameworks.add(package)

    doxygen = _doxygen_classes(repo_path)
    classes = {name for entry in file_entries for name in entry["classes"]}
    classes.update(doxygen.get("classes", []))

    result = {
        "language": "C++",
        "stats": {
            "files": len(files),
            "classes": len(classes),
            "local_edges": len(edges),
            "system_includes": system_includes,
        },
        "frameworks": sorted(frameworks),
        "cmake_packages": cmake_packages,
        "files": file_entries,
        "dependencies": edges,
        "doxygen": doxygen,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
