from typing import Any

from pydantic import BaseModel


class StructurizrArtifact(BaseModel):
    dsl: str
    workspace: dict[str, Any]
