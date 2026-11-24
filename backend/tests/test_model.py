from archdiscovery.pipeline.model import build_model


def deployment_payload() -> dict:
    return {
        "compose": [
            {
                "file": "compose.yaml",
                "services": [
                    {
                        "name": "api",
                        "image": None,
                        "build_context": "./api",
                        "dockerfile": "Dockerfile",
                        "ports": ["8000:8000"],
                        "depends_on": ["db"],
                    },
                    {
                        "name": "db",
                        "image": "postgres:16",
                        "build_context": None,
                        "dockerfile": None,
                        "ports": [],
                        "depends_on": [],
                    },
                ],
                "edges": [],
            }
        ],
        "dockerfiles": [],
        "kubernetes": [],
    }


def cpp_payload() -> dict:
    return {
        "files": [{"path": "api/main.cpp"}, {"path": "lib/foo.cpp"}],
        "dependencies": [{"from": "api/main.cpp", "to": "lib/foo.cpp", "kind": "include"}],
    }


def test_builds_c4_model() -> None:
    model = build_model(
        project_name="demo",
        technologies=[{"name": "C++"}],
        api_specs=[],
        deployment=deployment_payload(),
        cpp_artifact=cpp_payload(),
    )

    ids = {element.id for element in model.elements}
    assert "sys-demo" in ids
    assert "container-api" in ids
    assert "external-db" in ids
    assert "component-shared-lib" in ids

    pairs = {
        (relationship.source_id, relationship.destination_id)
        for relationship in model.relationships
    }
    assert ("container-api", "external-db") in pairs
    assert ("container-api", "component-shared-lib") in pairs

    assert model.deployment_nodes
    assert model.deployment_nodes[0].name == "Docker Compose"


def test_falls_back_to_single_container() -> None:
    model = build_model(
        project_name="empty",
        technologies=[],
        api_specs=[],
        deployment={"compose": [], "dockerfiles": [], "kubernetes": []},
        cpp_artifact=None,
    )
    containers = [element.id for element in model.elements if element.type == "container"]
    assert containers == ["container-app"]
