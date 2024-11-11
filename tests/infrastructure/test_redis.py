import logging
from typing import Dict, Any
from src.utils.queue_handler import RedisQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RedisTest')

def test_redis_connection():
    """Test Redis connection and pub/sub functionality."""
    print("\nTesting Redis Connection and Pub/Sub")
    print("=====================================")
    
    queue = None
    try:
        # Initialize Redis
        queue = RedisQueue()
        
        # Test basic connection
        print("\n1. Testing basic connection...")
        queue.redis.ping()
        print("✅ Basic connection successful")
        
        # Test pub/sub
        print("\n2. Testing pub/sub channels...")
        test_messages = []
        
        def test_callback(msg_type: str, data: Dict[str, Any]) -> None:
            test_messages.append((msg_type, data))
            print(f"✅ Received message: {msg_type} - {data}")
        
        # Subscribe to channels
        queue.subscribe(test_callback)
        print("✅ Subscribed to channels successfully")
        
        # Test publishing
        print("\n3. Testing message publishing...")
        test_data = {"test": "data", "timestamp": "2024-01-01"}
        queue.push_trade(test_data)
        print("✅ Published test message")
        
        # Get queue status
        print("\n4. Testing queue status...")
        status = queue.get_queue_status()
        print(f"✅ Queue status retrieved: {status}")
        
        print("\nAll Redis tests passed! ✨")
        
    except Exception as e:
        print(f"\n❌ Redis test failed: {e}")
        raise
    finally:
        if queue:
            queue.cleanup()
            print("\nRedis connection cleaned up")

if __name__ == "__main__":
    try:
        test_redis_connection()
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)