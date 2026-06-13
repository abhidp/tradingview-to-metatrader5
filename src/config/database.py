"""SQLite database configuration and shared engine/session factory.

This module replaces the previous PostgreSQL configuration. A single SQLite
file (see app.paths.get_db_path) backs the whole application. The engine is
created lazily so tests can point TV2MT5_DB_PATH at a temp file first.
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.paths import get_data_dir, get_db_path

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def _build_url() -> str:
    get_data_dir()  # ensure parent directory exists
    db_path = get_db_path().as_posix()
    return f"sqlite:///{db_path}"


def get_engine() -> Engine:
    """Return the process-wide SQLite engine, creating it on first use."""
    global _engine
    if _engine is None:
        url = _build_url()
        logger.info("Opening SQLite database at %s", url)
        _engine = create_engine(
            url,
            future=True,
            # SQLite + our threadpool executor: connections cross threads.
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Return a sessionmaker bound to the shared SQLite engine."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine(), future=True
        )
    return _SessionFactory

