"""Определение провайдера репозитория по URL."""

from urllib.parse import urlsplit

PROVIDERS = {"github", "gitlab", "other"}


def detect_provider(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if "github" in host:
        return "github"
    if "gitlab" in host:
        return "gitlab"
    return "other"


def auth_username(provider: str) -> str:
    """Username для Basic-auth при клонировании с токеном."""
    return "x-access-token" if provider == "github" else "oauth2"
