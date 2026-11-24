import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    repo_url: HttpUrl = Field(
        validation_alias=AliasChoices("repo_url", "gitlab_url"),
        description="HTTPS URL репозитория GitHub или GitLab",
    )
    default_branch: str | None = Field(
        default=None,
        max_length=255,
        description="Ветка; если не указана — определяется автоматически",
    )
    token: str | None = Field(default=None, min_length=1)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    repo_url: str
    provider: str
    default_branch: str | None
    created_at: datetime
