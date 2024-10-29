import os
import sys
from pathlib import Path
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.config.database import DB_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DB_Init')

def init_database():
    """Initialize the database with proper schema."""
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
        
        # Read and execute the SQL schema
        schema_path = Path(__file__).parent.parent.parent / 'init.sql'
        with open(schema_path, 'r') as f:
            sql_schema = f.read()
            
        logger.info("Initializing database schema...")
        cur.execute(sql_schema)
        logger.info("Database schema initialized successfully!")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    init_database()