"""Resolve where TV2MT5 stores its data (SQLite DB, logs)."""
import os
from pathlib import Path

APP_DIR_NAME = "TV2MT5"


def get_db_path() -> Path:
    """Return the SQLite database file path.

    Honours the TV2MT5_DB_PATH env override (used by tests and packaging).
    Defaults to %APPDATA%\\TV2MT5\\tv2mt5.db on Windows, else ~/.tv2mt5/tv2mt5.db.
    """
    override = os.getenv("TV2MT5_DB_PATH")
    if override:
        return Path(override)
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME / "tv2mt5.db"


def get_data_dir() -> Path:
    """Return (and create) the directory that holds the SQLite DB."""
    data_dir = get_db_path().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
