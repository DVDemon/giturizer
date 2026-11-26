from archdiscovery.pipeline.model import _endpoint_protocol, build_model


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

    by_pair = {(item.source_id, item.destination_id): item for item in model.relationships}
    database_edge = by_pair[("container-api", "external-db")]
    assert database_edge.protocol == "PostgreSQL"
    assert database_edge.transport == "TCP"
    assert database_edge.port == "5432"

    include_edge = by_pair[("container-api", "component-shared-lib")]
    assert include_edge.protocol == "include"
    assert include_edge.transport is None


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


def test_endpoint_protocol_inference() -> None:
    assert _endpoint_protocol({"image": "valkey/valkey:8.1.1-alpine"}) == (
        "RESP",
        "TCP",
        "6379",
    )
    assert _endpoint_protocol({"image": "postgres:14", "ports": ["15432:5432"]}) == (
        "PostgreSQL",
        "TCP",
        "5432",
    )
    assert _endpoint_protocol({"build_context": "./a", "ports": ["8080:8080"]}) == (
        "HTTP",
        "TCP",
        "8080",
    )


def test_deduplicates_containers_by_build_source() -> None:
    deployment = {
        "compose": [
            {
                "file": "docker-compose.yml",
                "services": [
                    {
                        "name": "app",
                        "image": None,
                        "build_context": "./services/app",
                        "dockerfile": "Dockerfile",
                        "build_source": "services/app/Dockerfile",
                        "ports": [],
                        "depends_on": [],
                    }
                ],
            },
            {
                "file": "services/app/docker-compose.yml",
                "services": [
                    {
                        "name": "app-local",
                        "image": None,
                        "build_context": ".",
                        "dockerfile": "Dockerfile",
                        "build_source": "services/app/Dockerfile",
                        "ports": ["8080:8080"],
                        "depends_on": [],
                    }
                ],
            },
        ],
        "dockerfiles": [],
        "kubernetes": [],
    }

    model = build_model(
        project_name="dedupe",
        technologies=[],
        api_specs=[],
        deployment=deployment,
        cpp_artifact=None,
    )

    containers = [element for element in model.elements if element.type == "container"]
    assert [container.name for container in containers] == ["app"]
    assert len(model.deployment_nodes[0].instances) == 1


def test_container_technology_is_inferred_per_build_context() -> None:
    deployment = {
        "compose": [
            {
                "file": "docker-compose.yml",
                "services": [
                    {
                        "name": "api",
                        "image": None,
                        "build_context": "./backend",
                        "dockerfile": "Dockerfile.api",
                        "ports": [],
                        "depends_on": [],
                    },
                    {
                        "name": "web",
                        "image": None,
                        "build_context": "./web",
                        "dockerfile": "Dockerfile",
                        "ports": [],
                        "depends_on": [],
                    },
                ],
            }
        ],
        "dockerfiles": [
            {"file": "backend/Dockerfile.api", "base_images": ["python:3.12-slim"]},
            {"file": "web/Dockerfile", "base_images": ["node:20-alpine", "nginx:alpine"]},
        ],
        "kubernetes": [],
    }
    model = build_model(
        project_name="polyglot",
        technologies=[
            {"name": "C++", "kind": "language"},
            {"name": "Python", "kind": "language"},
            {"name": "JavaScript/TypeScript", "kind": "language"},
        ],
        api_specs=[],
        deployment=deployment,
        cpp_artifact=None,
    )
    tech = {
        element.name: element.technology
        for element in model.elements
        if element.type == "container"
    }
    assert tech == {"api": "Python", "web": "JavaScript/TypeScript"}
