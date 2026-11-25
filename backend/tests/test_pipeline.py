import json
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
from archdiscovery.services.pipeline import execute_run
from archdiscovery.vcs.clone import CloneError


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
    (repo / "proto").mkdir()
    (repo / "proto" / "shop.proto").write_text(
        'syntax = "proto3";\nservice Shop { rpc Get (Req) returns (Res); }\n',
        encoding="utf-8",
    )
    (repo / "schema.graphql").write_text(
        "type Query {\n  shop: Shop\n}\ntype Shop {\n  id: ID\n}\n",
        encoding="utf-8",
    )
    (repo / "api").mkdir()
    (repo / "api" / "UserController.java").write_text(
        '@RestController\npublic class UserController {\n  @GetMapping("/users")\n}\n',
        encoding="utf-8",
    )
    return repo


def make_run(session: Session) -> AnalysisRun:
    project = Project(
        name="demo",
        repo_url="https://gitlab.example.com/group/demo",
        provider="gitlab",
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
    assert {spec.kind for spec in specs} == {"openapi", "grpc", "graphql", "annotations"}

    deployment = session.scalars(
        select(DeploymentModel).where(DeploymentModel.run_id == run.id)
    ).first()
    assert deployment is not None
    assert deployment.model["compose"]

    artifacts = session.scalars(select(RunArtifact).where(RunArtifact.run_id == run.id)).all()
    assert {artifact.kind for artifact in artifacts} == {"cpp", "archguard", "syntax"}
    assert run.stage == "done"
    assert run.progress == 100
    assert run.technologies_count >= 1
    assert run.services_count >= 1
    assert run.api_count >= 0


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
        json={"name": "demo", "repo_url": "https://gitlab.example.com/group/demo"},
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
    assert {spec["kind"] for spec in body["api_specs"]} == {
        "openapi",
        "grpc",
        "graphql",
        "annotations",
    }
    assert body["deployment"]["compose"]
    assert any(artifact["kind"] == "cpp" for artifact in body["artifacts"])

    report = client.get(f"/api/runs/{run['id']}/report")
    assert report.status_code == 200
    payload = report.json()
    assert set(payload) == {"technologies", "api", "deployment"}
    assert payload["technologies"]
    assert payload["api"]
    assert payload["deployment"]
    assert client.get(f"/api/runs/{run['id']}/structurizr").status_code == 404
    assert client.get(f"/api/runs/{run['id']}/graph/elements").status_code == 404


def test_repo_is_removed_after_run(tmp_path: Path, session: Session) -> None:
    repo = make_repo(tmp_path)
    run = make_run(session)

    def fake_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        shutil.copytree(repo, dest)
        return "abc123"

    def fake_dispatch(repo_path: Path, artifacts_dir: Path) -> dict:
        return {"language": "C++", "stats": {}}

    execute_run(
        session,
        run.id,
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=fake_dispatch,
    )

    assert not (tmp_path / "data" / "repos" / str(run.id)).exists()


def test_keep_repos_flag_keeps_clone(tmp_path: Path, session: Session) -> None:
    repo = make_repo(tmp_path)
    run = make_run(session)

    def fake_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        shutil.copytree(repo, dest)
        return "abc123"

    execute_run(
        session,
        run.id,
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=lambda *_: {"language": "C++", "stats": {}},
        keep_repos=True,
    )

    assert (tmp_path / "data" / "repos" / str(run.id)).exists()


def test_analyzer_failure_keeps_run_done_with_warning(tmp_path: Path, session: Session) -> None:
    repo = make_repo(tmp_path)
    run = make_run(session)

    def fake_clone(url: str, branch: str, token: str | None, dest: Path) -> str:
        shutil.copytree(repo, dest)
        return "abc123"

    def failing_dispatch(repo_path: Path, artifacts_dir: Path) -> dict:
        raise RuntimeError("tool crashed")

    result = execute_run(
        session,
        run.id,
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=failing_dispatch,
    )

    assert result is not None
    assert result.status == RunStatus.done

    warning = session.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id == run.id,
            RunArtifact.kind == "pipeline_warnings",
        )
    ).first()
    assert warning is not None
    assert "cpp analyzer" in json.dumps(warning.content)


def test_pipeline_detects_default_branch(tmp_path: Path, session: Session, monkeypatch) -> None:
    repo = make_repo(tmp_path)
    project = Project(
        name="github-demo",
        repo_url="https://github.com/owner/repo",
        provider="github",
        default_branch=None,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.commit()
    session.refresh(run)

    calls: list[str | None] = []

    def fake_detect(url: str, token: str | None) -> str:
        return "master"

    def fake_clone(url: str, branch: str | None, token: str | None, dest: Path) -> str:
        calls.append(branch)
        shutil.copytree(repo, dest)
        return "abc123"

    monkeypatch.setattr("archdiscovery.services.pipeline.detect_default_branch", fake_detect)

    result = execute_run(
        session,
        run.id,
        data_dir=tmp_path / "data",
        clone=fake_clone,
        dispatch=lambda *_: {"language": "C++", "stats": {}},
    )

    assert result is not None
    assert result.status == RunStatus.done
    assert calls == ["master"]
    session.refresh(project)
    assert project.default_branch == "master"
