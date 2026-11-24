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
