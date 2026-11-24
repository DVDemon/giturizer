from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from archdiscovery.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Iterator[Session]:
    """FastAPI-зависимость: сессия SQLAlchemy на запрос."""
    with SessionLocal() as session:
        yield session
