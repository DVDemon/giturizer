from pathlib import Path

from archdiscovery.pipeline.deployment_extract import extract_deployment


def test_extracts_compose(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text(
        "services:\n"
        "  api:\n"
        "    build: ./api\n"
        "    ports:\n"
        "      - 8000:8000\n"
        "    depends_on:\n"
        "      - db\n"
        "  db:\n"
        "    image: postgres:16\n",
        encoding="utf-8",
    )

    model = extract_deployment(tmp_path)

    assert model["compose"]
    services = model["compose"][0]["services"]
    names = {service["name"] for service in services}
    assert names == {"api", "db"}
    api = next(service for service in services if service["name"] == "api")
    assert api["build_context"] == "./api"
    assert api["ports"] == ["8000:8000"]
    assert {"from": "api", "to": "db", "type": "depends_on"} in model["compose"][0]["edges"]


def test_extracts_dockerfile(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(
        'FROM python:3.12-slim\nEXPOSE 8000\nCMD ["uvicorn"]\n', encoding="utf-8"
    )

    model = extract_deployment(tmp_path)

    assert model["dockerfiles"][0]["base_images"] == ["python:3.12-slim"]
    assert model["dockerfiles"][0]["exposed_ports"] == ["8000"]
