"""SQLAlchemy engine, session factory and table bootstrap."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
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

    target = bind or engine
    Base.metadata.create_all(bind=target)
    if target.dialect.name == "sqlite":
        existing = {column["name"] for column in inspect(target).get_columns("detections")}
        with target.begin() as connection:
            if "llm_assessment" not in existing:
                connection.execute(text("ALTER TABLE detections ADD COLUMN llm_assessment TEXT"))
            if "llm_status" not in existing:
                connection.execute(
                    text("ALTER TABLE detections ADD COLUMN llm_status VARCHAR(32) NOT NULL DEFAULT 'disabled'")
                )


def new_session() -> Session:
    return SessionLocal()
