"""Resolve where TV2MT5 stores its data (SQLite DB, logs)."""
import os
import shutil
from pathlib import Path

from app.resources import resource_path

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


def get_data_file(name: str, seed_name: str | None = None) -> Path:
    """Return the path to a mutable data file under %APPDATA%/TV2MT5/data/<name>.

    Creates the data dir. When seed_name is given and the target does not yet
    exist, copies the bundled default resource data/<seed_name> into place
    (first-run seeding). Honours TV2MT5_DATA_DIR for tests/packaging.
    """
    override = os.getenv("TV2MT5_DATA_DIR")
    data_dir = Path(override) if override else get_data_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / name
    if seed_name and not target.exists():
        seed = resource_path(f"data/{seed_name}")
        if seed.exists():
            shutil.copyfile(seed, target)
    return target
