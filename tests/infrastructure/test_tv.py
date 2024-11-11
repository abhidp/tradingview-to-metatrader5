import logging
import asyncio
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
        
        print("\nTradingView service tests completed")
        
    except Exception as e:
        print(f"\n❌ TradingView service test failed: {e}")
        raise
    finally:
        if tv_service:
            await tv_service.cleanup()
            print("\nTradingView service cleaned up")

def test_tv():
    """Wrapper to run async test."""
    asyncio.run(test_tv_service())

if __name__ == "__main__":
    try:
        test_tv()
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)