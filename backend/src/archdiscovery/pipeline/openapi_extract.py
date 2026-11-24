import json
from pathlib import Path

import yaml

OPENAPI_NAMES = {
    "openapi.yaml",
    "openapi.yml",
    "openapi.json",
    "swagger.yaml",
    "swagger.yml",
    "swagger.json",
}


def _load(path: Path):
    if path.suffix.lower() == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None


def extract_openapi_specs(repo_path: Path) -> list[dict]:
    specs: list[dict] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name not in OPENAPI_NAMES and not name.startswith(("openapi", "swagger")):
            continue
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        document = _load(path)
        if not isinstance(document, dict):
            continue
        if "openapi" not in document and "swagger" not in document:
            continue
        if "paths" not in document:
            continue
        specs.append(
            {
                "kind": "openapi",
                "name": str(path.relative_to(repo_path)),
                "spec": document,
            }
        )
    return specs
