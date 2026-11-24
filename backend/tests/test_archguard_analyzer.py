import json
import subprocess
from pathlib import Path

from archdiscovery.analyzer.archguard import analyze_archguard


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "services" / "gateway" / "src").mkdir(parents=True)
    (repo / "services" / "capability-service").mkdir(parents=True)
    (repo / "services" / "frontend").mkdir(parents=True)
    (repo / "services" / "gateway" / "src" / "A.java").write_text("class A {}", encoding="utf-8")
    (repo / "services" / "frontend" / "App.tsx").write_text(
        "import { api } from './api';\n", encoding="utf-8"
    )
    (repo / "services" / "capability-service" / "B.java").write_text("class B {}", encoding="utf-8")
    (repo / ".gitmodules").write_text(
        '[submodule "services/gateway"]\n'
        "\tpath = services/gateway\n"
        "\turl = https://github.com/o/gateway.git\n\n"
        '[submodule "services/capability-service"]\n'
        "\tpath = services/capability-service\n"
        "\turl = https://github.com/o/capability.git\n\n"
        '[submodule "services/frontend"]\n'
        "\tpath = services/frontend\n"
        "\turl = https://github.com/o/frontend.git\n",
        encoding="utf-8",
    )
    return repo


def test_archguard_summarizes_submodules(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)

    monkeypatch.setattr("archdiscovery.analyzer.archguard._prepare_workdir", lambda workdir: None)

    def fake_run(repo_path, language, workdir, timeout):
        (workdir / "0_codes.json").write_text(
            json.dumps(
                [
                    {"FilePath": str(repo / "services/gateway/src/A.java")},
                    {"FilePath": "/src/services/capability-service/B.java"},
                ]
            ),
            encoding="utf-8",
        )
        (workdir / "0_apis.json").write_text("[]", encoding="utf-8")
        (workdir / "0_databases.json").write_text("[]", encoding="utf-8")
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    monkeypatch.setattr("archdiscovery.analyzer.archguard._run_scanner", fake_run)

    output = tmp_path / "out" / "archguard.json"
    result = analyze_archguard(repo, output, ["Java"])

    assert result["languages"]["Java"]["codes"] == 2
    assert result["summary"]["submodules"] == 3
    assert result["summary"]["submodules_analyzed"] == 3
    assert result["fallback"]["modules"] == {"services/frontend": 1}
    assert result["summary"]["fallback_files"] == 1
    assert set(result["summary"]["modules"]) == {
        "services/gateway",
        "services/capability-service",
    }
    assert output.exists()


def test_archguard_records_language_error(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setattr("archdiscovery.analyzer.archguard._prepare_workdir", lambda workdir: None)

    def failing_run(repo_path, language, workdir, timeout):
        return subprocess.CompletedProcess([], 1, stdout="", stderr="NPE in parser")

    monkeypatch.setattr("archdiscovery.analyzer.archguard._run_scanner", failing_run)

    result = analyze_archguard(repo, tmp_path / "out" / "archguard.json", ["TypeScript"])

    assert result["languages"] == {}
    assert result["errors"][0]["language"] == "TypeScript"
    assert "NPE" in result["errors"][0]["error"]
