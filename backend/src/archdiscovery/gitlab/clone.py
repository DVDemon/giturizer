import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


class CloneError(RuntimeError):
    pass


def auth_url(url: str, token: str | None) -> str:
    """Подставляет access token в HTTPS-URL GitLab (Basic auth, user=oauth2)."""
    if not token:
        return url
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        return url
    netloc = f"oauth2:{quote(token, safe='')}@{parts.hostname}"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _redact(text: str, token: str | None) -> str:
    if not token:
        return text
    return text.replace(token, "***").replace(quote(token, safe=""), "***")


def clone_repository(
    url: str,
    branch: str,
    token: str | None,
    dest: Path,
    timeout: int = 600,
) -> str:
    """Shallow-клон ветки в dest; возвращает commit sha."""
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
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise CloneError(f"clone timed out after {timeout}s") from exc

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "git clone failed").strip()
        raise CloneError(_redact(message, token))

    commit = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return commit.stdout.strip()
