"""Run all infrastructure tests."""
import asyncio
import logging

from .test_db import test_database
from .test_mt5 import test_mt5_connection
from .test_redis import test_redis_connection
from .test_tv import test_tv_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('InfraTest')

async def run_all_tests():
    """Run all infrastructure tests asynchronously."""
    print("\n🚀 Running All Infrastructure Tests")
    print("================================")
    
    try:
        # Database test
        print("\n📊 Testing Database...")
        test_database()
        
        # Redis test
        print("\n📡 Testing Redis...")
        test_redis_connection()
        
        # MT5 test
        print("\n💱 Testing MT5...")
        mt5_success = await test_mt5_connection()
        if not mt5_success:
            return False
        
        # TradingView test
        print("\n📈 Testing TradingView Service...")
        tv_success = await test_tv_service()
        if not tv_success:
            return False
        
        print("\n✨ All infrastructure tests completed!")
        return True
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        return False

def main():
    """Run the test suite."""
    try:
        success = asyncio.run(run_all_tests())
        if not success:
            exit(1)
    except KeyboardInterrupt:
        print("\nTests cancelled by user")
        exit(1)
    except Exception as e:
        print(f"Test suite failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()