from archdiscovery.config import Settings


def test_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "archdiscovery"
    assert settings.database_url.startswith("postgresql")
    assert settings.redis_url.startswith("redis://")


def test_cors_origins_non_empty() -> None:
    assert Settings().cors_origins
