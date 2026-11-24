from pathlib import Path

from archdiscovery.pipeline.deployment_extract import extract_deployment
from archdiscovery.pipeline.graphql_extract import extract_graphql_specs
from archdiscovery.pipeline.grpc_extract import extract_grpc_specs
from archdiscovery.pipeline.openapi_extract import extract_openapi_specs


def test_malformed_inputs_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "openapi.yaml").write_text("openapi: [unclosed\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text("services: [\n", encoding="utf-8")
    (tmp_path / "bad.proto").write_text("service {\n", encoding="utf-8")
    (tmp_path / "schema.graphql").write_text("type {\n", encoding="utf-8")

    assert extract_openapi_specs(tmp_path) == []
    assert extract_grpc_specs(tmp_path) == []
    assert extract_graphql_specs(tmp_path) == []

    model = extract_deployment(tmp_path)
    assert model["compose"] == []
    assert model["summary"]["compose_services"] == 0
