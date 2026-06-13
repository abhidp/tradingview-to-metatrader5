import os
from pathlib import Path

from app.paths import get_db_path, get_data_dir


def test_db_path_honours_env_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setenv("TV2MT5_DB_PATH", str(target))
    assert get_db_path() == target


def test_data_dir_is_created(monkeypatch, tmp_path):
    monkeypatch.setenv("TV2MT5_DB_PATH", str(tmp_path / "sub" / "db.sqlite"))
    data_dir = get_data_dir()
    assert data_dir.exists()
    assert data_dir == (tmp_path / "sub")


from sqlalchemy import text  # noqa: E402


def test_get_engine_creates_sqlite_file(temp_db_path):
    from src.config.database import get_engine, get_session_factory

    engine = get_engine()
    assert engine.url.get_backend_name() == "sqlite"

    Session = get_session_factory()
    session = Session()
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        session.close()


def test_init_db_creates_trades_table(temp_db_path):
    from sqlalchemy import inspect

    from src.config.database import get_engine
    from src.models.database import init_db

    init_db()
    inspector = inspect(get_engine())
    assert "trades" in inspector.get_table_names()
