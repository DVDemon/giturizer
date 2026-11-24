import subprocess

import pytest

from archdiscovery.db.models import AnalysisRun, ArchitectureSnapshot, Project
from archdiscovery.services.c4_graphviz import GraphvizError, build_c4_dot, render_c4_svg

WORKSPACE = {
    "model": {
        "softwareSystems": [
            {
                "id": "shop",
                "name": 'Shop "Core"',
                "containers": [
                    {"id": "api", "name": "API", "technology": "FastAPI"},
                    {"id": "db", "name": "Database", "technology": "PostgreSQL"},
                ],
            },
            {"id": "auth", "name": "Auth", "technology": "OIDC"},
        ],
        "relationships": [
            {
                "id": "r1",
                "sourceId": "api",
                "destinationId": "db",
                "description": "reads/writes",
                "properties": {"protocol": "PostgreSQL"},
            },
            {
                "id": "r2",
                "sourceId": "shop",
                "destinationId": "auth",
                "description": "uses",
            },
        ],
    }
}


def test_build_c4_dot_contains_clusters_and_relations() -> None:
    dot = build_c4_dot(WORKSPACE)

    assert "digraph c4" in dot
    assert "subgraph cluster_shop" in dot
    assert 'label="Shop \\"Core\\""' in dot
    assert "API\\n[FastAPI]" in dot
    assert "Database\\n[PostgreSQL]" in dot
    assert "ctr_api -> ctr_db" in dot
    assert "ltail=cluster_shop" in dot


def test_render_c4_svg_calls_dot(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["input"] = kwargs["input"]
        return subprocess.CompletedProcess(arguments, 0, stdout="<svg/>", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert render_c4_svg(WORKSPACE) == "<svg/>"
    assert captured["arguments"] == ["fdp", "-Tsvg"]
    assert "digraph c4" in captured["input"]


def test_render_c4_svg_raises_when_dot_is_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(GraphvizError, match="graphviz"):
        render_c4_svg(WORKSPACE)


def test_render_c4_svg_raises_on_dot_error(monkeypatch) -> None:
    def fake_run(arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 1, stdout="", stderr="syntax error")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(GraphvizError, match="syntax error"):
        render_c4_svg(WORKSPACE)


def test_c4_svg_endpoint(client, session, monkeypatch) -> None:
    project = Project(name="demo", repo_url="https://github.com/o/r", provider="github")
    session.add(project)
    session.flush()
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.flush()
    session.add(
        ArchitectureSnapshot(
            project_id=project.id,
            run_id=run.id,
            dsl="",
            workspace=WORKSPACE,
        )
    )
    session.commit()

    monkeypatch.setattr(
        "archdiscovery.api.routes.structurizr.render_c4_svg",
        lambda workspace: "<svg>ok</svg>",
    )

    response = client.get(f"/api/runs/{run.id}/c4.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text == "<svg>ok</svg>"


def test_c4_svg_endpoint_returns_503_on_graphviz_error(client, session, monkeypatch) -> None:
    project = Project(name="demo", repo_url="https://github.com/o/r", provider="github")
    session.add(project)
    session.flush()
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.flush()
    session.add(
        ArchitectureSnapshot(
            project_id=project.id,
            run_id=run.id,
            dsl="",
            workspace=WORKSPACE,
        )
    )
    session.commit()

    def fail(workspace):
        raise GraphvizError("dot not found")

    monkeypatch.setattr("archdiscovery.api.routes.structurizr.render_c4_svg", fail)

    response = client.get(f"/api/runs/{run.id}/c4.svg")

    assert response.status_code == 503
    assert "graphviz" in response.json()["detail"]


def test_build_c4_dot_scopes_and_dedupes_externals() -> None:
    workspace = {
        "model": {
            "softwareSystems": [
                {
                    "id": "root",
                    "name": "Root",
                    "containers": [{"id": "api", "name": "API"}],
                },
                {"id": "db-a", "name": "PostgreSQL", "technology": "15"},
                {"id": "db-b", "name": "PostgreSQL", "technology": "15"},
                {"id": "unused", "name": "Unused"},
            ],
            "relationships": [
                {"sourceId": "api", "destinationId": "db-a", "description": "uses"},
                {"sourceId": "api", "destinationId": "db-b", "description": "uses"},
            ],
        }
    }

    dot = build_c4_dot(workspace)

    assert dot.count('label="PostgreSQL') == 1
    assert "unused" not in dot
