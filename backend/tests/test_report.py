from archdiscovery.pipeline.report import build_report


def test_build_report_groups_api_and_deployment() -> None:
    report = build_report(
        technologies=[
            {
                "name": "Maven",
                "kind": "build",
                "version": "3.9.9",
                "evidence": "services/shop/pom.xml",
            }
        ],
        api_specs=[
            {
                "kind": "annotations",
                "name": "services/shop/main.py",
                "spec": {
                    "file": "services/shop/main.py",
                    "framework": "fastapi",
                    "endpoints": [
                        {"method": "GET", "path": "/items"},
                        {"method": "POST", "path": "/items"},
                    ],
                },
            },
            {
                "kind": "openapi",
                "name": "openapi.yaml",
                "spec": {
                    "paths": {
                        "/health": {
                            "get": {
                                "tags": ["shop"],
                                "summary": "Health check",
                            }
                        }
                    }
                },
            },
        ],
        deployment={
            "compose": [
                {
                    "services": [
                        {
                            "name": "db",
                            "image": "postgres:15-alpine",
                            "ports": ["5432:5432"],
                            "depends_on": [],
                        }
                    ]
                }
            ],
            "dockerfiles": [
                {
                    "file": "Dockerfile",
                    "base_images": ["python:3.12-slim"],
                    "exposed_ports": ["8000"],
                }
            ],
        },
    )

    assert report["technologies"] == [
        {
            "name": "Maven",
            "type": "build",
            "version": "3.9.9",
            "description": "services/shop/pom.xml",
        }
    ]
    services = {item["service"]: item["methods"] for item in report["api"]}
    assert set(services) == {"shop"}
    assert {method["operation"] for method in services["shop"]} >= {
        "GET /items",
        "POST /items",
    }
    assert services["shop"][0]["technology"] in {"fastapi", "OpenAPI"}
    assert any(method["operation"] == "GET /health" for method in services["shop"])

    methods = {item["method"]: item["services"] for item in report["deployment"]}
    assert methods["Docker Compose"][0]["image"] == "postgres"
    assert methods["Docker Compose"][0]["image_version"] == "15-alpine"
    assert methods["Docker Compose"][0]["ports"] == ["5432:5432"]
    assert methods["Dockerfile"][0]["image"] == "python"
    assert methods["Dockerfile"][0]["image_version"] == "3.12-slim"
