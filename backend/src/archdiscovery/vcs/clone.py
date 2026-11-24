"""Клонирование публичных и приватных репозиториев GitHub/GitLab."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from archdiscovery.vcs.provider import auth_username, detect_provider


class CloneError(RuntimeError):
    pass


def auth_url(url: str, token: str | None, provider: str | None = None) -> str:
    """Подставляет access token в HTTPS-URL (Basic auth)."""
    if not token:
        return url
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        return url
    provider = provider or detect_provider(url)
    username = auth_username(provider)
    netloc = f"{username}:{quote(token, safe='')}@{parts.hostname}"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _redact(text: str, token: str | None) -> str:
    if not token:
        return text
    return text.replace(token, "***").replace(quote(token, safe=""), "***")


def _run(arguments: list[str], timeout: int) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, env=env)


def detect_default_branch(
    url: str,
    token: str | None = None,
    timeout: int = 60,
) -> str:
    """Определяет ветку по умолчанию через `git ls-remote --symref ... HEAD`."""
    provider = detect_provider(url)
    try:
        proc = _run(
            ["git", "ls-remote", "--symref", auth_url(url, token, provider), "HEAD"],
            timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "main"

    if proc.returncode != 0:
        return "main"

    match = re.search(r"ref:\s+refs/heads/(\S+)\s+HEAD", proc.stdout)
    if match:
        return match.group(1)
    match = re.search(r"refs/heads/(\S+)\s+HEAD", proc.stdout)
    return match.group(1) if match else "main"


def _clone(
    url: str,
    branch: str,
    token: str | None,
    dest: Path,
    timeout: int,
) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--branch",
        branch,
        auth_url(url, token),
        str(dest),
    ]
    try:
        proc = _run(command, timeout)
    except subprocess.TimeoutExpired as exc:
        raise CloneError(f"clone timed out after {timeout}s") from exc

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "git clone failed").strip()
        raise CloneError(_redact(message, token))


def clone_repository(
    url: str,
    branch: str | None,
    token: str | None,
    dest: Path,
    timeout: int = 600,
) -> str:
    """Shallow-клон ветки в dest; возвращает commit sha.

    Если ветка не указана — определяется по умолчанию у провайдера.
    Если указанная ветка отсутствует — один раз пробуем ветку по умолчанию.
    """
    resolved_branch = branch or detect_default_branch(url, token)
    try:
        _clone(url, resolved_branch, token, dest, timeout)
    except CloneError as exc:
        if branch and _is_missing_branch(str(exc)):
            detected = detect_default_branch(url, token)
            if detected and detected != resolved_branch:
                resolved_branch = detected
                _clone(url, resolved_branch, token, dest, timeout)
            else:
                raise
        else:
            raise

    commit = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return commit.stdout.strip()


def _is_missing_branch(message: str) -> bool:
    lowered = message.lower()
    return "remote branch" in lowered and "not found" in lowered
