"""Shared pytest fixtures for TV2MT5 tests."""
import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)


@pytest.fixture
def temp_db_path(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file for the duration of a test."""
    db_file = tmp_path / "test_tv2mt5.db"
    monkeypatch.setenv("TV2MT5_DB_PATH", str(db_file))
    yield db_file
    # Reset the lazy engine singletons so each test gets a fresh engine.
    import src.config.database as _db
    _db._engine = None
    _db._SessionFactory = None


@pytest.fixture
def event_loop():
    """Provide a fresh asyncio event loop per test (pytest-asyncio)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()