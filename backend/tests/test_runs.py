import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from archdiscovery.services.runs import execute_stub


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "demo", "gitlab_url": "https://gitlab.example.com/group/demo"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_run_queued(client: TestClient) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/runs",
        json={"config": {"branch": "main"}},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["config"] == {"branch": "main"}
    assert body["started_at"] is None
    assert body["finished_at"] is None


def test_run_completed_by_stub(client: TestClient, session: Session) -> None:
    project_id = create_project(client)
    run = client.post(f"/api/projects/{project_id}/runs", json={}).json()

    execute_stub(session, uuid.UUID(run["id"]))

    fetched = client.get(f"/api/runs/{run['id']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "done"
    assert body["started_at"] is not None
    assert body["finished_at"] is not None


def test_list_runs(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(f"/api/projects/{project_id}/runs", json={})
    client.post(f"/api/projects/{project_id}/runs", json={})

    response = client.get(f"/api/projects/{project_id}/runs")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_run_for_missing_project_returns_404(client: TestClient) -> None:
    response = client.post(f"/api/projects/{uuid.uuid4()}/runs", json={})
    assert response.status_code == 404


def test_get_missing_run_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/runs/{uuid.uuid4()}").status_code == 404
