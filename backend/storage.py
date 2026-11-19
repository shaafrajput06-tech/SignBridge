"""SQLAlchemy storage layer; SQLite is the default and URL can select PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
default_file = PROJECT_ROOT / "data" / "signbridge.sqlite3"
default_file.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.environ.get("SIGNBRIDGE_DATABASE_URL", f"sqlite:///{default_file.as_posix()}")
engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False, "timeout": 30}
try:
    engine = create_engine(DATABASE_URL, **engine_options)
except ModuleNotFoundError as error:
    if DATABASE_URL.startswith("postgresql"):
        raise RuntimeError(
            "PostgreSQL support is optional. Install it with: python -m pip install -r requirements-postgres.txt "
            "and use a URL that starts with postgresql+psycopg://"
        ) from error
    raise
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class RecognitionHistory(Base):
    __tablename__ = "recognition_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vocabulary_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class TrainingExample(Base):
    __tablename__ = "training_examples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vocabulary_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    participant: Mapped[str] = mapped_column(String(120), nullable=False)
    session_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    features_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


def initialize_database() -> None:
    Base.metadata.create_all(engine)
