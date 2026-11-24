from pathlib import Path

from archdiscovery.pipeline.openapi_extract import extract_openapi_specs


def test_extracts_openapi_yaml(tmp_path: Path) -> None:
    (tmp_path / "openapi.yaml").write_text(
        "openapi: 3.0.0\ninfo:\n  title: demo\npaths: {}\n", encoding="utf-8"
    )

    specs = extract_openapi_specs(tmp_path)

    assert len(specs) == 1
    assert specs[0]["kind"] == "openapi"
    assert specs[0]["name"] == "openapi.yaml"
    assert specs[0]["spec"]["openapi"] == "3.0.0"


def test_ignores_yaml_without_openapi(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("service:\n  port: 80\n", encoding="utf-8")
    assert extract_openapi_specs(tmp_path) == []
