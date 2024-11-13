"""MT5 connection test module."""
import asyncio
import logging

import MetaTrader5 as mt5

from src.config.mt5_config import MT5_CONFIG
from src.services.mt5_service import MT5Service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MT5Test')

async def test_mt5_connection():
    """Test MT5 connection and basic functionality."""
    print("\nTesting MT5 Connection")
    print("=====================")
    
    mt5_service = None
    try:
        # Initialize MT5
        print("\n1. Testing MT5 initialization...")
        mt5_service = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
        
        if await mt5_service.async_initialize():
            print("✅ MT5 initialization successful")
        else:
            raise Exception("MT5 initialization failed")
        
        # Test symbol mapping
        print("\n2. Testing symbol mapping...")
        test_symbols = ['BTCUSD', 'EURUSD', 'XAUUSD']
        for sym in test_symbols:
            mapped = mt5_service.map_symbol(sym)
            print(f"✅ {sym} -> {mapped}")
        
        # Test market data access
        print("\n3. Testing market data access...")
        for sym in test_symbols:
            mapped_sym = mt5_service.map_symbol(sym)
            symbol_info = await asyncio.to_thread(mt5.symbol_info, mapped_sym)
            if symbol_info:
                print(f"✅ Selected {mapped_sym} (Bid: {symbol_info.bid}, Ask: {symbol_info.ask})")
            else:
                print(f"⚠️  No data for {mapped_sym}")
        
        print("\nAll MT5 tests passed! ✨")
        return True
        
    except Exception as e:
        logger.error(f"MT5 test failed: {e}")
        return False
    finally:
        if mt5_service:
            mt5_service.cleanup()
            print("\nMT5 connection cleaned up")

if __name__ == "__main__":
    asyncio.run(test_mt5_connection())
