from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from archdiscovery.crypto import DEFAULT_TOKEN_KEY


class Settings(BaseSettings):
    """Настройки сервиса, читаются из переменных окружения."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_name: str = "archdiscovery"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://archdiscovery:archdiscovery@localhost:5432/archdiscovery"
    )
    redis_url: str = "redis://localhost:6379/0"
    data_dir: str = "/data"

    gitlab_url: str = "https://gitlab.example.com"
    gitlab_token: str | None = None
    token_encryption_key: str = DEFAULT_TOKEN_KEY

    clone_timeout: int = 1200
    analyzer_timeout: int = 3600
    keep_repos: bool = False

    cors_origins: list[str] = ["http://localhost:8080", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
