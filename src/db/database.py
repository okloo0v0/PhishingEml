"""SQLAlchemy engine, session factory and table bootstrap."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config import get_settings

Base = declarative_base()


def create_engine_for(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, future=True)
    return create_engine(url, future=True)


engine = create_engine_for(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(bind=None) -> None:
    import src.db.models  # noqa: F401  register all tables on Base

    Base.metadata.create_all(bind=bind or engine)


def new_session() -> Session:
    return SessionLocal()
