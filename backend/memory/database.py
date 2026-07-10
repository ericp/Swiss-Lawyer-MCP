"""Database utilities for SQLite memory."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy import create_engine

DEFAULT_SQLITE_PATH = Path("data/sqlite/memory.db")
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy memory models."""


def create_memory_engine(database_url: str = DEFAULT_DATABASE_URL) -> Engine:
    """Create a SQLAlchemy engine with SQLite foreign keys enabled."""

    url = make_url(database_url)
    connect_args = {"check_same_thread": False} if url.get_backend_name() == "sqlite" else {}
    engine = create_engine(database_url, future=True, connect_args=connect_args)

    if url.get_backend_name() == "sqlite":
        _enable_sqlite_foreign_keys(engine)

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create an injectable SQLAlchemy session factory."""

    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionFactory = Callable[[], Session]
