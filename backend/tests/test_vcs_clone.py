import subprocess
from pathlib import Path

from archdiscovery.vcs.clone import (
    _redact,
    auth_url,
    clone_repository,
    detect_default_branch,
)
from archdiscovery.vcs.provider import detect_provider


def test_detect_provider() -> None:
    assert detect_provider("https://github.com/o/r") == "github"
    assert detect_provider("https://gitlab.com/g/r") == "gitlab"
    assert detect_provider("https://example.com/g/r") == "other"


def test_auth_url_gitlab() -> None:
    url = auth_url("https://gitlab.com/group/project.git", "glpat-abc")
    assert url.startswith("https://oauth2:glpat-abc@gitlab.com/group/project.git")


def test_auth_url_github() -> None:
    url = auth_url("https://github.com/owner/project.git", "ghp-abc")
    assert url.startswith("https://x-access-token:ghp-abc@github.com/owner/project.git")


def test_auth_url_without_token_is_unchanged() -> None:
    url = "https://gitlab.com/group/project.git"
    assert auth_url(url, None) == url


def test_auth_url_preserves_port() -> None:
    url = auth_url("https://gitlab.local:8443/group/project.git", "token")
    assert url.startswith("https://oauth2:token@gitlab.local:8443/")


def test_redact_removes_token_from_messages() -> None:
    cleaned = _redact("fatal: auth failed for glpat-secret", "glpat-secret")
    assert "glpat-secret" not in cleaned
    assert "***" in cleaned


def test_detect_default_branch_parses_symref(monkeypatch) -> None:
    def fake_run(arguments, **kwargs):
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout="ref: refs/heads/master\tHEAD\nabc123\tHEAD\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert detect_default_branch("https://github.com/o/r") == "master"


def test_detect_default_branch_falls_back_to_main(monkeypatch) -> None:
    def fake_run(arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 128, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert detect_default_branch("https://github.com/o/r") == "main"


def test_clone_includes_submodules(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        if arguments[1] == "clone":
            Path(arguments[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(arguments, 0, stdout="abcdef\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    sha = clone_repository("https://github.com/o/r", "main", None, tmp_path / "repo")

    assert sha == "abcdef"
    clone_command = calls[0]
    assert "--recurse-submodules" in clone_command
    assert "--shallow-submodules" in clone_command
