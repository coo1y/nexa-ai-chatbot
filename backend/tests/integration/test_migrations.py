"""Alembic migrations create exactly the schema the ORM models describe."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.db.base import Base

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(tmp_path: Path) -> tuple[Config, str]:
    url = f"sqlite:///{tmp_path}/migrations.db"
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("sqlite://", "sqlite+aiosqlite://"))
    config.attributes["configure_logger"] = False
    return config, url


def test_upgrade_matches_models_and_downgrades(alembic_config: tuple[Config, str]) -> None:
    config, url = alembic_config
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
    command.downgrade(config, "base")
    with engine.connect() as conn:
        tables = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert {t[0] for t in tables} <= {"alembic_version"}
