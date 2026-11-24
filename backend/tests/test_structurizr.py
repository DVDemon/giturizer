from archdiscovery.pipeline.model import build_model
from archdiscovery.pipeline.structurizr import (
    generate_dsl,
    generate_json,
    validate_workspace,
)


def make_model():
    deployment = {
        "compose": [
            {
                "services": [
                    {
                        "name": "api",
                        "build_context": "./api",
                        "dockerfile": "Dockerfile",
                        "image": None,
                        "depends_on": ["db"],
                    },
                    {
                        "name": "db",
                        "image": "postgres:16",
                        "build_context": None,
                        "dockerfile": None,
                        "depends_on": [],
                    },
                ],
                "edges": [],
            }
        ],
        "dockerfiles": [],
        "kubernetes": [],
    }
    cpp = {"files": [{"path": "api/main.cpp"}], "dependencies": []}
    return build_model(
        project_name="demo",
        technologies=[{"name": "C++"}],
        api_specs=[{"kind": "openapi", "name": "openapi.yaml", "spec": {}}],
        deployment=deployment,
        cpp_artifact=cpp,
    )


def test_json_is_valid_and_nested() -> None:
    workspace = generate_json(make_model())

    validate_workspace(workspace)

    names = [system["name"] for system in workspace["model"]["softwareSystems"]]
    assert "demo" in names
    assert "db" in names

    system = next(item for item in workspace["model"]["softwareSystems"] if item["name"] == "demo")
    assert [container["name"] for container in system["containers"]] == ["api"]
    assert workspace["model"]["relationships"]
    assert workspace["model"]["deploymentNodes"]


def test_dsl_contains_elements() -> None:
    dsl = generate_dsl(make_model())

    assert dsl.startswith("workspace ")
    assert 'softwareSystem "demo"' in dsl
    assert 'container "api"' in dsl
    assert "->" in dsl
    assert 'deploymentEnvironment "Production"' in dsl
    assert "systemLandscape" in dsl
