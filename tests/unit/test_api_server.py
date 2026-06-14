from datetime import datetime, timedelta


def test_recent_trades_newest_first_and_limited(temp_db_path):
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.api.trades import recent_trades

    init_db()
    db = DatabaseHandler()
    base = datetime(2026, 6, 14, 12, 0, 0)
    for i in range(3):
        db.save_trade({
            "trade_id": f"T{i}",
            "order_id": f"O{i}",
            "instrument": "EURUSD",
            "side": "buy",
            "quantity": "0.10",
            "type": "market",
            "ask_price": "1.1000",
            "bid_price": "1.0998",
            "status": "completed",
            "tv_request": "{}",
            "tv_response": "{}",
            "created_at": base + timedelta(minutes=i),
        })

    rows = recent_trades(limit=2)
    assert len(rows) == 2
    assert rows[0]["trade_id"] == "T2"  # newest first
    assert rows[1]["trade_id"] == "T1"
    assert rows[0]["instrument"] == "EURUSD"
    db.cleanup()
