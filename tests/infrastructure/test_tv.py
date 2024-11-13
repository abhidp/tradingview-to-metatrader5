"""Test TradingView service functionality."""
import asyncio
import logging

from src.services.tradingview_service import TradingViewService
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TVTest')

async def test_tv_service():
    """Test TradingView service functionality."""
    print("\nTesting TradingView Service")
    print("==========================")
    
    tv_service = None
    try:
        # Initialize service
        print("\n1. Testing service initialization...")
        tv_service = TradingViewService(token_manager=GLOBAL_TOKEN_MANAGER)
        print("✅ Service initialized")
        
        # Test token management
        print("\n2. Testing token management...")
        token = tv_service.token_manager.get_token()
        if token:
            print("✅ Token available")
        else:
            print("❌ No token available - please log into TradingView first")
            return False
        
        print("\nTradingView service tests completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ TradingView service test failed: {e}")
        return False
    finally:
        if tv_service:
            await tv_service.cleanup()
            print("\nTradingView service cleaned up")

async def run_test():
    """Run the async test."""
    try:
        return await test_tv_service()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False

def test_tv():
    """Run the test synchronously."""
    return asyncio.run(run_test())

if __name__ == "__main__":
    try:
        success = test_tv()
        if not success:
            exit(1)
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        exit(1)
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)
