import shutil
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from archdiscovery.services.pipeline import execute_run


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "demo", "repo_url": "https://gitlab.example.com/group/demo"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def make_repo(path: Path) -> Path:
    repo = path / "repo"
    repo.mkdir()
    (repo / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.12)\n", encoding="utf-8")
    (repo / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    return repo


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


def test_run_completed_by_pipeline(client: TestClient, session: Session, tmp_path: Path) -> None:
    project_id = create_project(client)
    run = client.post(f"/api/projects/{project_id}/runs", json={}).json()
    repo = make_repo(tmp_path)

    def fake_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        shutil.copytree(repo, dest)
        return "deadbeef"

    def fake_dispatch(repo_path: Path, artifacts_dir: Path) -> dict:
        return {"language": "C++", "files": [], "stats": {"files": 1}}

    result = execute_run(
        session,
        uuid.UUID(run["id"]),
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=fake_dispatch,
    )
    assert result is not None
    assert result.status.value == "done"

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
