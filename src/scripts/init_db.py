import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.config.database import DB_CONFIG


def reset_database():
    """Reset database with fresh schema and optimized indexes."""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Drop existing trades table
        print("Dropping existing tables...")
        cur.execute("DROP TABLE IF EXISTS trades CASCADE;")

        # Create fresh trades table with JSONB instead of JSON for better performance
        print("Creating trades table...")
        cur.execute("""
        CREATE TABLE trades (
            id SERIAL PRIMARY KEY,
            trade_id VARCHAR(50) UNIQUE NOT NULL,
            order_id VARCHAR(50),
            position_id VARCHAR(50),
            mt5_ticket VARCHAR(50),
            mt5_position VARCHAR(50),
            
            instrument VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            quantity DECIMAL NOT NULL,
            type VARCHAR(20) NOT NULL,
            
            ask_price DECIMAL,
            bid_price DECIMAL,
            execution_price DECIMAL,
            take_profit DECIMAL,
            stop_loss DECIMAL,
            tp_order_id VARCHAR(50),
            sl_order_id VARCHAR(50),
            trailing_stop_pips DECIMAL,
                    
            status VARCHAR(20) NOT NULL DEFAULT 'new',
            error_message TEXT,
            is_closed BOOLEAN DEFAULT FALSE,
            close_requested_at TIMESTAMP WITH TIME ZONE,
            execution_time_ms INTEGER,
            
            tv_request JSONB,
            tv_response JSONB,
            execution_data JSONB,
            mt5_response JSONB,
            
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE,
            executed_at TIMESTAMP WITH TIME ZONE,
            closed_at TIMESTAMP WITH TIME ZONE
        );
        """)

        # Create optimized indexes
        print("Creating indexes...")
        
        # Primary lookup indexes
        cur.execute("""
            CREATE UNIQUE INDEX idx_trade_id ON trades(trade_id);
            CREATE INDEX idx_order_id ON trades(order_id);
            CREATE INDEX idx_position_id ON trades(position_id);
            CREATE INDEX idx_mt5_ticket ON trades(mt5_ticket);
        """)
        
        # Performance optimization indexes
        cur.execute("""
            -- Status-based queries
            CREATE INDEX idx_status ON trades(status);
            CREATE INDEX idx_status_created_at ON trades(status, created_at);
            
            -- Time-based queries
            CREATE INDEX idx_created_at ON trades(created_at);
            CREATE INDEX idx_executed_at ON trades(executed_at);
            CREATE INDEX idx_closed_at ON trades(closed_at);
            
            -- Trade analysis indexes
            CREATE INDEX idx_instrument_side ON trades(instrument, side);
            CREATE INDEX idx_execution_time ON trades(execution_time_ms);
            
            -- Compound indexes for common queries
            CREATE INDEX idx_status_instrument ON trades(status, instrument);
            CREATE INDEX idx_is_closed_created_at ON trades(is_closed, created_at);
            
            -- JSONB indexes for faster JSON operations
            CREATE INDEX idx_tv_request_gin ON trades USING gin(tv_request);
            CREATE INDEX idx_execution_data_gin ON trades USING gin(execution_data);
        """)

        # Create partial indexes for active trades
        cur.execute("""
            -- Partial index for open trades
            CREATE INDEX idx_active_trades ON trades(created_at) 
            WHERE status IN ('new', 'pending', 'executing');
            
            -- Partial index for non-closed positions
            CREATE INDEX idx_open_positions ON trades(mt5_ticket) 
            WHERE is_closed = FALSE;
        """)

        print("Database reset completed successfully!")
        print("\nOptimized indexes have been created for:")
        print("✓ Fast trade lookups by ID/ticket")
        print("✓ Efficient status and time-based queries")
        print("✓ Quick instrument and execution analysis")
        print("✓ Optimized JSON field searches")
        print("✓ Active trade filtering")

    except Exception as e:
        print(f"Reset failed: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("\n=== Resetting Database ===")
    confirm = input("This will delete all existing trade data. Continue? (Y/N): ")
    if confirm.lower() == 'y':
        reset_database()
    else:
        print("Operation cancelled.")