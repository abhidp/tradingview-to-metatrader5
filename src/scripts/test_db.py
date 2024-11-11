import sys
from pathlib import Path
import psycopg2
import logging
from dotenv import load_dotenv
import os

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

# Load environment variables
env_path = Path(project_root) / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_required_env(key: str) -> str:
    """Get required environment variable."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def test_docker_db():
    print("\nTesting Docker database connection...")
    
    # Load environment variables
    load_dotenv()
    
    # Get connection parameters from environment
    params = {
        'host': get_required_env('DB_HOST'),
        'port': get_required_env('DB_PORT'),
        'database': get_required_env('DB_NAME'),
        'user': get_required_env('DB_USER'),
        'password': get_required_env('DB_PASSWORD')
    }
    
    print("\nConnection parameters:")
    for key, value in params.items():
        if key != 'password':
            print(f"{key}: {value}")
    
    try:
        print("\nAttempting connection...")
        conn = psycopg2.connect(**params)
        
        print("✅ Connected to database !!")
        
        # Test basic query
        cur = conn.cursor()
        cur.execute('SELECT version();')
        version = cur.fetchone()
        print(f"\nPostgreSQL version: {version[0]}")
        
        # Test permissions
        print("\nTesting table creation permission...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS connection_test (
                id serial PRIMARY KEY,
                test_time timestamp DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("✅ Table creation successful !!")
        
        # Clean up test table
        cur.execute("DROP TABLE connection_test;")
        conn.commit()
        print("✅ Test cleanup successful !!")
        
    except Exception as e:
        print(f"\n❌ Connection test failed:")
        print(f"Error: {str(e)}")
        print("\nDebug information:")
        print(f"Connection string: postgresql://{params['user']}:***@{params['host']}:{params['port']}/{params['database']}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
            print("\nConnection closed.")

if __name__ == "__main__":
    test_docker_db()