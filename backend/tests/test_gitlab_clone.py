from archdiscovery.gitlab.clone import auth_url


def test_auth_url_injects_token() -> None:
    url = auth_url("https://gitlab.com/group/project.git", "glpat-abc")
    assert url.startswith("https://oauth2:glpat-abc@gitlab.com/group/project.git")


def test_auth_url_without_token_is_unchanged() -> None:
    url = "https://gitlab.com/group/project.git"
    assert auth_url(url, None) == url


def test_auth_url_preserves_port() -> None:
    url = auth_url("https://gitlab.local:8443/group/project.git", "token")
    assert url.startswith("https://oauth2:token@gitlab.local:8443/")
