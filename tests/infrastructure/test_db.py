import logging

from sqlalchemy import text

from src.utils.database_handler import DatabaseHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DBTest')

def test_database():
    """Test database connection."""
    print("\nTesting Database Connection")
    print("=========================")
    
    db = None
    try:
        print("\n1. Initializing database handler...")
        db = DatabaseHandler()
        print("✅ Handler initialized")
        
        print("\n2. Testing database connection...")
        with db.get_db() as session:
            result = session.execute(text("SELECT 1"))
            print("✅ Connection successful")
            
        print("\nAll database tests passed! ✨")
        
    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        raise
    finally:
        if db:
            db.cleanup()
            print("\nDatabase connection cleaned up")

if __name__ == "__main__":
    try:
        test_database()
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)