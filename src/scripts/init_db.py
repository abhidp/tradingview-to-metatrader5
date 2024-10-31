import sys
from pathlib import Path
import logging
from sqlalchemy import create_engine, text

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.config.database import DB_CONFIG
from src.models.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DB_Init')

def initialize_database():
    """Initialize database with fresh tables."""
    try:
        # Drop existing tables if they exist
        logger.info("Dropping existing tables...")
        Base.metadata.drop_all(bind=engine)
        
        # Create tables
        logger.info("Creating tables...")
        Base.metadata.create_all(bind=engine)
        
        # Create indexes
        with engine.connect() as conn:
            logger.info("Creating indexes...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(created_at);
                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
            """))
            conn.commit()
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

if __name__ == "__main__":
    print("\n=== Initializing Database ===")
    initialize_database()
    print("\nDone!")