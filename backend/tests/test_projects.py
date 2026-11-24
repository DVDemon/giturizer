import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from archdiscovery.db import models


def payload(**overrides):
    data = {
        "name": "demo",
        "repo_url": "https://gitlab.example.com/group/demo",
        "default_branch": "main",
        "token": "secret-token",
    }
    data.update(overrides)
    return data


def test_create_project(client: TestClient) -> None:
    response = client.post("/api/projects", json=payload())
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "demo"
    assert body["repo_url"] == "https://gitlab.example.com/group/demo"
    assert body["provider"] == "gitlab"
    assert "token" not in body
    assert body["id"]


def test_token_is_encrypted(client: TestClient, session: Session) -> None:
    body = client.post("/api/projects", json=payload()).json()
    project = session.get(models.Project, uuid.UUID(body["id"]))
    assert project is not None
    assert project.token_encrypted
    assert project.token_encrypted != "secret-token"


def test_list_and_get_project(client: TestClient) -> None:
    created = client.post("/api/projects", json=payload()).json()

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert [item["id"] for item in body["items"]] == [created["id"]]

    fetched = client.get(f"/api/projects/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_delete_project(client: TestClient) -> None:
    created = client.post("/api/projects", json=payload()).json()
    assert client.delete(f"/api/projects/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{created['id']}").status_code == 404


def test_get_missing_project_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/projects/{uuid.uuid4()}")
    assert response.status_code == 404


def test_github_public_project_without_token(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "public-github",
            "repo_url": "https://github.com/owner/public-repo",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "github"
    assert body["default_branch"] is None
    assert "token" not in body


def test_legacy_gitlab_url_field_is_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        json={
            "name": "legacy",
            "gitlab_url": "https://gitlab.com/group/legacy",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["repo_url"] == "https://gitlab.com/group/legacy"
    assert body["provider"] == "gitlab"


def test_projects_pagination_and_filters(client: TestClient) -> None:
    for name in ("alpha", "beta", "gamma"):
        client.post(
            "/api/projects",
            json={"name": name, "repo_url": f"https://github.com/o/{name}"},
        )

    first = client.get("/api/projects", params={"per_page": 2, "page": 1}).json()
    assert first["total"] == 3
    assert len(first["items"]) == 2
    assert first["per_page"] == 2

    second = client.get("/api/projects", params={"per_page": 2, "page": 2}).json()
    assert len(second["items"]) == 1

    filtered = client.get("/api/projects", params={"search": "bet"}).json()
    assert [item["name"] for item in filtered["items"]] == ["beta"]

    github = client.get("/api/projects", params={"provider": "github"}).json()
    assert github["total"] == 3

    invalid = client.get("/api/projects", params={"per_page": 0})
    assert invalid.status_code == 422


def test_projects_sort_and_last_scan(client: TestClient, session: Session) -> None:
    from datetime import UTC, datetime

    ids = {}
    for name in ("zeta", "alpha"):
        body = client.post(
            "/api/projects",
            json={"name": name, "repo_url": f"https://github.com/o/{name}"},
        ).json()
        ids[name] = uuid.UUID(body["id"])

    session.add(
        models.AnalysisRun(
            project_id=ids["zeta"],
            created_at=datetime(2026, 11, 24, 10, 0, tzinfo=UTC),
        )
    )
    session.commit()

    by_name = client.get("/api/projects", params={"sort": "name", "order": "asc"}).json()
    assert [item["name"] for item in by_name["items"]] == ["alpha", "zeta"]

    by_scan = client.get("/api/projects", params={"sort": "last_scan_at", "order": "desc"}).json()
    assert by_scan["items"][0]["name"] == "zeta"
    assert by_scan["items"][0]["last_scan_at"] is not None
    assert by_scan["items"][1]["last_scan_at"] is None
