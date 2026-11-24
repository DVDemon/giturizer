from typing import Any

from pydantic import BaseModel

from archdiscovery.schemas.run import RunRead


class ApiSpecRead(BaseModel):
    kind: str
    name: str
    spec: dict[str, Any]


class ArtifactRead(BaseModel):
    kind: str
    path: str
    content: dict[str, Any]


class RunResults(BaseModel):
    run: RunRead
    technologies: list[dict[str, Any]]
    api_specs: list[ApiSpecRead]
    deployment: dict[str, Any] | None
    artifacts: list[ArtifactRead]
