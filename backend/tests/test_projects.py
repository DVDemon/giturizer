import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from archdiscovery.db import models


def payload(**overrides):
    data = {
        "name": "demo",
        "gitlab_url": "https://gitlab.example.com/group/demo",
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
    assert body["gitlab_url"] == "https://gitlab.example.com/group/demo"
    assert "token" not in body
    assert body["id"]


def test_token_is_encrypted(client: TestClient, session: Session) -> None:
    body = client.post("/api/projects", json=payload()).json()
    project = session.get(models.Project, uuid.UUID(body["id"]))
    assert project is not None
    assert project.gitlab_token_encrypted
    assert project.gitlab_token_encrypted != "secret-token"


def test_list_and_get_project(client: TestClient) -> None:
    created = client.post("/api/projects", json=payload()).json()

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

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
