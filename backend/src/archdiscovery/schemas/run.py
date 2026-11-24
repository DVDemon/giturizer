import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from archdiscovery.db.models import RunStatus


class RunCreate(BaseModel):
    commit_sha: str | None = Field(default=None, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: RunStatus
    commit_sha: str | None
    config: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
