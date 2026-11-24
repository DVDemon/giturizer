from pathlib import Path

from archdiscovery.pipeline.tech_detect import detect_technologies


def test_detects_cpp_stack(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text(
        "find_package(userver COMPONENTS core REQUIRED)\n", encoding="utf-8"
    )
    (tmp_path / "main.cpp").write_text(
        "#include <userver/utils/daemon_run.hpp>\n", encoding="utf-8"
    )
    (tmp_path / "Dockerfile").write_text("FROM ubuntu:22.04\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text(
        "services:\n  db:\n    image: postgres:14\n", encoding="utf-8"
    )

    names = {technology.name for technology in detect_technologies(tmp_path)}

    assert {"C++", "CMake", "userver", "Docker", "Docker Compose", "PostgreSQL"} <= names


def test_ignores_vcs_and_build_dirs(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.cpp").write_text("class Hidden {};\n", encoding="utf-8")
    (tmp_path / "main.cpp").write_text("int main() {}\n", encoding="utf-8")

    technologies = detect_technologies(tmp_path)
    cpp = next(technology for technology in technologies if technology.name == "C++")
    assert "1 files" in cpp.evidence
