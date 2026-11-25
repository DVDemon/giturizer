from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from archdiscovery.api import deps
from archdiscovery.api.main import app
from archdiscovery.db import models  # noqa: F401  (регистрирует таблицы в metadata)
from archdiscovery.db.base import Base


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with factory() as db_session:
        yield db_session


@pytest.fixture()
def client(session: Session) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        yield session

    def override_publisher():
        return lambda run_id: None

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_publisher] = override_publisher
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


ARCHGUARD_STUB = {
    "tool": "archguard",
    "version": "2.3.0",
    "languages": {"Java": {"codes": 1, "apis": 0, "databases": 0, "modules": {}}},
    "summary": {
        "codes": 1,
        "apis": 0,
        "databases": 0,
        "modules": {},
        "submodules": 0,
        "submodules_analyzed": 0,
        "submodule_paths": [],
    },
    "apis": [],
    "databases": [],
    "errors": [],
}


@pytest.fixture(autouse=True)
def stub_archguard_dispatch(monkeypatch):
    """Не ходим в Celery/ArchGuard из юнит-тестов пайплайна."""
    monkeypatch.setattr(
        "archdiscovery.services.pipeline.dispatch_archguard_analyzer",
        lambda *args, **kwargs: ARCHGUARD_STUB,
    )


SYNTAX_STUB = {
    "tool": "tree-sitter",
    "version": "0.27.0",
    "languages": ["java"],
    "handlers": [
        {
            "method": "GET",
            "path": "/users",
            "handler": {
                "file": "api/UserController.java",
                "line": 3,
                "symbol": "users",
                "class": "UserController",
                "language": "java",
                "framework": "Spring",
            },
            "source": {"file": "api/UserController.java", "line": 3},
            "framework": "Spring",
            "confidence": 0.95,
        }
    ],
    "stats": {"files": 1, "handlers": 1, "languages": ["java"]},
    "errors": [],
}


@pytest.fixture(autouse=True)
def stub_syntax_dispatch(monkeypatch):
    """Не ходим в Celery/Tree-sitter из юнит-тестов пайплайна."""
    monkeypatch.setattr(
        "archdiscovery.services.pipeline.dispatch_syntax_analyzer",
        lambda *args, **kwargs: SYNTAX_STUB,
    )
