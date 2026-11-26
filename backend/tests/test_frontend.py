from pathlib import Path

from archdiscovery.analyzer.frontend.analyze import analyze_frontend


def test_extracts_react_api_calls_and_resolves_gateway(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"18.0.0","react-dom":"18.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "const.ts").write_text(
        "const PREFIX_GATEWAY = '/api-gateway/';\n"
        "const PREFIX_GATEWAY_USER = '/user/api/';\n"
        "export const GATEWAY_USER_URL = IS_DEV ? GATEWAY_DIRECT_USER_LINK : PREFIX_GATEWAY_USER;\n"
        "export const GATEWAY_URL = IS_DEV ? GATEWAY_DIRECT_LINK : PREFIX_GATEWAY;\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "api" / "user.ts").write_text(
        "import Api from 'utils/api/axiosWrapper';\n"
        "import { GATEWAY_URL, GATEWAY_USER_URL } from './const';\n"
        "export const getUser = (id: number) => Api.get({\n"
        "  url: `${GATEWAY_USER_URL}v1/user/${id}`,\n"
        "});\n"
        "export const getRoles = () => Api.get({\n"
        "  url: `${GATEWAY_URL}auth/v1/roles`,\n"
        "});\n"
        "export const create = () => axios.post('/api/v1/items', {});\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "api" / "mock.ts").write_text(
        "export const mock = () => Api.get({ url: '/mock' });\n",
        encoding="utf-8",
    )

    result = analyze_frontend(tmp_path, tmp_path / "frontend.json")

    calls = result["api_calls"]
    assert len(calls) == 3
    by_path = {(call["method"], call["normalized_path"]): call for call in calls}
    assert ("GET", "/api/v1/user/{}") in by_path
    assert by_path[("GET", "/api/v1/user/{}")]["service"] == "fdm-auth"
    assert ("GET", "/api/v1/roles") in by_path
    assert by_path[("GET", "/api/v1/roles")]["service"] == "fdm-auth"
    assert ("POST", "/api/v1/items") in by_path
    assert not any(call["url_template"] == "/mock" for call in calls)
    assert result["stats"]["frontends"] == 1


def test_frontend_endpoint(client, session) -> None:
    from archdiscovery.db.models import AnalysisRun, Project, RunArtifact

    project = Project(name="front", repo_url="https://github.com/o/r", provider="github")
    session.add(project)
    session.commit()
    session.refresh(project)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RunArtifact(
            run_id=run.id,
            kind="frontend",
            path="",
            content={
                "frontends": [{"root": "web", "name": "web", "framework": "react"}],
                "api_calls": [{"method": "GET", "normalized_path": "/api/v1/user"}],
                "stats": {"frontends": 1, "api_calls": 1},
                "errors": [],
            },
        )
    )
    session.commit()

    response = client.get(f"/api/runs/{run.id}/frontend")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["api_calls"][0]["normalized_path"] == "/api/v1/user"


def test_react_router_page_hook_api_flow(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"18.0.0","react-dom":"18.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "src" / "api" / "user").mkdir(parents=True)
    (tmp_path / "src" / "api" / "queries").mkdir(parents=True)
    (tmp_path / "src" / "pages" / "users").mkdir(parents=True)
    (tmp_path / "src" / "router").mkdir(parents=True)
    (tmp_path / "src" / "api" / "const.ts").write_text(
        "const PREFIX_GATEWAY = '/api-gateway/';\n"
        "export const GATEWAY_URL = IS_DEV ? GATEWAY_DIRECT_LINK : PREFIX_GATEWAY;\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "api" / "user" / "index.ts").write_text(
        "import Api from 'utils/api/axiosWrapper';\n"
        "import { GATEWAY_URL } from '../const';\n"
        "export const getUser = () => Api.get({ url: `${GATEWAY_URL}auth/v1/user` });\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "api" / "queries" / "user.ts").write_text(
        "import { useQuery } from '@tanstack/react-query';\n"
        "import { getUser } from 'api/user';\n"
        "export const useUser = () => useQuery({ queryFn: () => getUser() });\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "pages" / "users" / "index.tsx").write_text(
        "import { useUser } from 'api/queries/user';\n"
        "export const UsersPage = () => { const { data } = useUser(); return null; };\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "router" / "index.tsx").write_text(
        "import { Route } from 'react-router-dom';\n"
        "import { UsersPage } from 'pages/users';\n"
        'export const Router = () => <Route path="/users" element={<UsersPage />} />;\n',
        encoding="utf-8",
    )

    result = analyze_frontend(tmp_path, tmp_path / "frontend.json")

    assert result["routes"] == [
        {
            "path": "/users",
            "component": "UsersPage",
            "file": "src/router/index.tsx",
            "line": 3,
            "component_file": "src/pages/users/index.tsx",
        }
    ]
    assert len(result["ui_flows"]) == 1
    calls = result["ui_flows"][0]["calls"]
    assert len(calls) == 1
    assert calls[0]["normalized_path"] == "/api/v1/user"
    assert calls[0]["service"] == "fdm-auth"
    assert result["stats"]["routes"] == 1
