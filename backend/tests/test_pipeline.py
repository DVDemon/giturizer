import shutil
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import (
    AnalysisRun,
    ApiSpec,
    DeploymentModel,
    Project,
    RunArtifact,
    RunStatus,
    TechRegistry,
)
from archdiscovery.gitlab.clone import CloneError
from archdiscovery.services.pipeline import execute_run


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "svc").mkdir(parents=True)
    (repo / "CMakeLists.txt").write_text(
        "find_package(userver COMPONENTS core REQUIRED)\n", encoding="utf-8"
    )
    (repo / "svc" / "main.cpp").write_text(
        "#include <userver/utils/daemon_run.hpp>\n", encoding="utf-8"
    )
    (repo / "openapi.yaml").write_text("openapi: 3.0.0\npaths: {}\n", encoding="utf-8")
    (repo / "compose.yaml").write_text("services:\n  api:\n    image: nginx\n", encoding="utf-8")
    return repo


def make_run(session: Session) -> AnalysisRun:
    project = Project(
        name="demo",
        gitlab_url="https://gitlab.example.com/group/demo",
        default_branch="main",
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def test_execute_run_persists_results(tmp_path: Path, session: Session) -> None:
    repo = make_repo(tmp_path)
    run = make_run(session)

    def fake_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        shutil.copytree(repo, dest)
        return "abc123"

    def fake_dispatch(repo_path: Path, artifacts_dir: Path) -> dict:
        return {"language": "C++", "stats": {"files": 1}, "dependencies": []}

    result = execute_run(
        session,
        run.id,
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=fake_dispatch,
    )

    assert result is not None
    assert result.status == RunStatus.done
    assert result.commit_sha == "abc123"

    technologies = session.scalars(
        select(TechRegistry).where(TechRegistry.run_id == run.id)
    ).first()
    assert technologies is not None
    assert "C++" in {item["name"] for item in technologies.technologies}

    specs = session.scalars(select(ApiSpec).where(ApiSpec.run_id == run.id)).all()
    assert [spec.kind for spec in specs] == ["openapi"]

    deployment = session.scalars(
        select(DeploymentModel).where(DeploymentModel.run_id == run.id)
    ).first()
    assert deployment is not None
    assert deployment.model["compose"]

    artifacts = session.scalars(select(RunArtifact).where(RunArtifact.run_id == run.id)).all()
    assert [artifact.kind for artifact in artifacts] == ["cpp"]


def test_execute_run_marks_failed_on_clone_error(tmp_path: Path, session: Session) -> None:
    run = make_run(session)

    def failing_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        raise CloneError("authentication failed")

    result = execute_run(session, run.id, data_dir=tmp_path / "data", clone=failing_clone)

    assert result is not None
    assert result.status == RunStatus.failed
    assert "authentication failed" in (result.error or "")
    assert result.finished_at is not None


def test_results_endpoint(client: TestClient, session: Session, tmp_path: Path) -> None:
    project = client.post(
        "/api/projects",
        json={"name": "demo", "gitlab_url": "https://gitlab.example.com/group/demo"},
    ).json()
    run = client.post(f"/api/projects/{project['id']}/runs", json={}).json()

    repo = make_repo(tmp_path)

    def fake_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        shutil.copytree(repo, dest)
        return "abc123"

    def fake_dispatch(repo_path: Path, artifacts_dir: Path) -> dict:
        return {"language": "C++", "stats": {"files": 1}, "dependencies": []}

    execute_run(
        session,
        uuid.UUID(run["id"]),
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=fake_dispatch,
    )

    response = client.get(f"/api/runs/{run['id']}/results")
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["status"] == "done"
    assert any(item["name"] == "C++" for item in body["technologies"])
    assert body["api_specs"][0]["kind"] == "openapi"
    assert body["deployment"]["compose"]
    assert any(artifact["kind"] == "cpp" for artifact in body["artifacts"])
