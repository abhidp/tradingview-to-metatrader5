import os
import sys
from pathlib import Path
import logging
from datetime import datetime, timedelta

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.models.database import SessionLocal, Trade
from sqlalchemy import desc

def check_database():
    """Check database status and recent trades."""
    db = SessionLocal()
    try:
        # Check recent trades
        print("\nRecent Trades:")
        print("-------------")
        recent_trades = db.query(Trade).order_by(desc(Trade.created_at)).limit(5).all()
        
        if not recent_trades:
            print("No trades found")
        else:
            for trade in recent_trades:
                print(f"\nTrade ID: {trade.trade_id}")
                print(f"Order ID: {trade.order_id}")
                print(f"Instrument: {trade.instrument}")
                print(f"Side: {trade.side}")
                print(f"Quantity: {trade.quantity}")
                print(f"Status: {trade.status}")
                print(f"Created: {trade.created_at}")
        
        # Check trade counts
        total_trades = db.query(Trade).count()
        pending_trades = db.query(Trade).filter(Trade.status == 'pending').count()
        executed_trades = db.query(Trade).filter(Trade.status == 'executed').count()
        
        print("\nTrade Statistics:")
        print("----------------")
        print(f"Total trades: {total_trades}")
        print(f"Pending trades: {pending_trades}")
        print(f"Executed trades: {executed_trades}")
        
    finally:
        db.close()

if __name__ == "__main__":
    print("\n=== Database Check Tool ===")
    check_database()
    print("\nCheck complete!")