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


import asyncio  # noqa: E402
from datetime import datetime  # noqa: E402


async def test_database_handler_save_and_get(temp_db_path):
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler

    init_db()
    db = DatabaseHandler()

    trade_data = {
        "trade_id": "TV_TEST_1",
        "order_id": "O1",
        "instrument": "EURUSD",
        "side": "buy",
        "quantity": "0.10",
        "type": "market",
        "ask_price": "1.1000",
        "bid_price": "1.0999",
        "take_profit": None,
        "stop_loss": None,
        "status": "pending",
        "tv_request": {"raw": "req"},
        "tv_response": {"raw": "resp"},
        "created_at": datetime.utcnow(),
    }

    await db.async_save_trade(trade_data)
    fetched = await db.async_get_trade("TV_TEST_1")

    assert fetched is not None
    assert fetched["instrument"] == "EURUSD"
    assert fetched["side"] == "buy"
    db.cleanup()


async def test_update_trade_status_accepts_datetime_for_datetime_columns(temp_db_path):
    """Regression: close/closed_at status writes must pass datetime objects, not
    ISO strings. SQLite DateTime columns reject strings (Postgres tolerated them)."""
    import pytest
    from datetime import datetime, timezone

    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler

    init_db()
    db = DatabaseHandler()
    base = {
        "trade_id": "TV_CLOSE_1", "order_id": "O9", "instrument": "BTCUSD",
        "side": "buy", "quantity": "0.01", "type": "market",
        "ask_price": "60000", "bid_price": "59990",
        "status": "pending", "tv_request": {}, "tv_response": {},
        "created_at": datetime.utcnow(),
    }
    await db.async_save_trade(base)

    # datetime OBJECT works (the fixed code path)
    await db.async_update_trade_status(
        "TV_CLOSE_1", "closed",
        {"is_closed": True,
         "close_requested_at": datetime.utcnow(),
         "closed_at": datetime.now(timezone.utc)},
    )
    fetched = await db.async_get_trade("TV_CLOSE_1")
    assert fetched["status"] == "closed"

    # ISO STRING must raise — documents why .isoformat() was the bug
    with pytest.raises(Exception):
        await db.async_update_trade_status(
            "TV_CLOSE_1", "closed", {"closed_at": "2020-01-01T00:00:00"}
        )
    db.cleanup()
