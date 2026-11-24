from archdiscovery.gitlab.clone import _redact, auth_url


def test_auth_url_injects_token() -> None:
    url = auth_url("https://gitlab.com/group/project.git", "glpat-abc")
    assert url.startswith("https://oauth2:glpat-abc@gitlab.com/group/project.git")


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
