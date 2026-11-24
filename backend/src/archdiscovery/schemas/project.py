import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    gitlab_url: HttpUrl
    default_branch: str = Field(default="main", min_length=1, max_length=255)
    token: str | None = Field(default=None, min_length=1)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    gitlab_url: str
    default_branch: str
    created_at: datetime
