import sys
from pathlib import Path
import logging
from datetime import datetime
import argparse
from sqlalchemy import inspect, text

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.models.database import Base, engine, SessionLocal
from src.config.database import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DBTools')

def check_database():
    """Check database status and recent trades."""
    db = SessionLocal()
    try:
        # Check recent trades
        print("\nRecent Trades:")
        print("-" * 50)
        trades = db.execute(text("""
            SELECT trade_id, instrument, side, quantity, status, mt5_ticket, created_at 
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 5
        """)).fetchall()
        
        if not trades:
            print("No trades found")
        else:
            for trade in trades:
                print(f"\nTrade ID: {trade.trade_id}")
                print(f"Instrument: {trade.instrument}")
                print(f"Side: {trade.side}")
                print(f"Quantity: {trade.quantity}")
                print(f"Status: {trade.status}")
                print(f"MT5 Ticket: {trade.mt5_ticket}")
                print(f"Created: {trade.created_at}")
        
        # Check trades by status
        counts = db.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM trades 
            GROUP BY status
        """)).fetchall()
        
        print("\nTrade Statistics:")
        print("-" * 50)
        for status, count in counts:
            print(f"{status}: {count}")
        
    finally:
        db.close()

def verify_schema():
    """Verify database schema."""
    inspector = inspect(engine)
    
    print("\nDatabase Schema:")
    print("-" * 50)
    
    tables = inspector.get_table_names()
    for table in tables:
        print(f"\nTable: {table}")
        
        print("  Columns:")
        for column in inspector.get_columns(table):
            print(f"    - {column['name']}: {column['type']}")
        
        print("\n  Indexes:")
        for index in inspector.get_indexes(table):
            print(f"    - {index['name']}: {index['column_names']}")

def reset_database():
    """Reset database schema."""
    confirm = input("\n⚠️ This will delete all data. Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return
    
    print("\nResetting database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Create indexes
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(created_at);
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
        """))
        conn.commit()
    
    print("Database reset complete!")

def main():
    parser = argparse.ArgumentParser(description='Database management tools')
    parser.add_argument('action', choices=['check', 'verify', 'reset'], 
                       help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'check':
        check_database()
    elif args.action == 'verify':
        verify_schema()
    elif args.action == 'reset':
        reset_database()

if __name__ == "__main__":
    print("\n=== Database Management Tools ===")
    main()