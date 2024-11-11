import logging

from .test_db import test_database
from .test_redis import test_redis_connection
from .test_mt5 import test_mt5_connection
from .test_tv import test_tv

def run_all_tests():
    """Run all infrastructure tests."""
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
        test_mt5_connection()
        
        # TradingView test
        print("\n📈 Testing TradingView Service...")
        test_tv()
        
        print("\n✨ All infrastructure tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        raise

if __name__ == "__main__":
    run_all_tests()