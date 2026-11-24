"""Переносимые типы SQLAlchemy: JSONB на PostgreSQL, JSON на остальных диалектах."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONType = JSON().with_variant(JSONB(), "postgresql")
