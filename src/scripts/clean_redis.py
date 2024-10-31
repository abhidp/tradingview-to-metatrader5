import sys
from pathlib import Path
import redis

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

def clean_redis():
    """Clean all trade queues."""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Clean all queues
        queues = [
            'trades:pending',
            'trades:processing',
            'trades:completed',
            'trades:failed'
        ]
        
        for queue in queues:
            if r.exists(queue):
                r.delete(queue)
                print(f"Cleared queue: {queue}")
        
        print("\nRedis queues cleaned successfully!")
        
    except Exception as e:
        print(f"Error cleaning Redis: {e}")

if __name__ == "__main__":
    print("\nCleaning Redis queues...")
    clean_redis()