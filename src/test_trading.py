import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import time
import json

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.services.trade_executor import TradeExecutor
from src.utils.symbol_mapper import SymbolMapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TradingTest')

def print_dict(d: dict, indent: int = 0):
    """Pretty print nested dictionary."""
    for key, value in d.items():
        if isinstance(value, dict):
            print("  " * indent + f"{key}:")
            print_dict(value, indent + 1)
        else:
            print("  " * indent + f"{key}: {value}")

def test_account_connection(executor):
    """Test MT5 account connection and permissions."""
    print("\n=== Testing Account Connection ===")
    status = executor.verify_account()
    
    if 'error' in status:
        print(f"Connection Error: {status['error']}")
        return False
        
    print("Account Details:")
    print_dict(status)
    
    # Verify critical conditions
    if status.get('status') != 'connected':
        print("Error: Terminal not connected!")
        return False
    
    if not status.get('trading_enabled'):
        print("Warning: Trading is not enabled!")
        return False
        
    return True

def test_symbol_info(executor, symbols):
    """Test symbol information and pricing."""
    print("\n=== Testing Symbol Information ===")
    
    results = {}
    for symbol in symbols:
        info = executor.get_symbol_info(symbol)
        print(f"\n{symbol}:")
        if 'error' in info:
            print(f"Error: {info['error']}")
            results[symbol] = False
        else:
            print_dict(info)
            results[symbol] = True
            
            # Validate price data
            if info.get('bid', 0) <= 0 or info.get('ask', 0) <= 0:
                print(f"Warning: Invalid prices for {symbol}")
                results[symbol] = False
    
    return all(results.values())

def test_market_order(executor, symbol, side, volume):
    """Test market order execution."""
    print(f"\n=== Testing Market Order: {side.upper()} {volume} {symbol} ===")
    
    trade_request = {
        "instrument": symbol,
        "side": side,
        "qty": volume,
        "type": "market",
        "requestId": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    print("Sending order:")
    print_dict(trade_request)
    
    result = executor.execute_market_order(trade_request)
    
    print("\nOrder Result:")
    print_dict(result)
    
    success = 'error' not in result
    if not success:
        print(f"Trade failed: {result.get('error')}")
    else:
        print(f"Trade successful! Order ID: {result.get('order_id')}")
    
    return success
def test_market_order_and_close(executor, symbol, volume):
    """Test market order execution and closing."""
    print(f"\n=== Testing Market Order Cycle: {symbol} {volume} ===")
    
    # 1. Place Buy Order
    trade_request = {
        "instrument": symbol,
        "side": "buy",
        "qty": volume,
        "type": "market",
        "requestId": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    print("\nPlacing Buy Order:")
    print_dict(trade_request)
    
    result = executor.execute_market_order(trade_request)
    if 'error' in result:
        print(f"Trade failed: {result['error']}")
        return False
        
    print("\nBuy Order Result:")
    print_dict(result)
    
    # Wait a few seconds
    print("\nWaiting 10 seconds...")
    time.sleep(10)
    
    # 2. Get Position Info
    position = executor.get_position(symbol)
    if not position:
        print("Error: Cannot find opened position")
        return False
        
    print("\nOpen Position:")
    print_dict(position)
    
    # 3. Close Position
    print("\nClosing position...")
    close_result = executor.close_position(symbol)
    
    print("\nClose Result:")
    print_dict(close_result)
    
    if 'error' in close_result:
        print(f"Close failed: {close_result['error']}")
        return False
        
    return True

def main():
    # Initialize
    executor = TradeExecutor(SymbolMapper())
    
    try:
        # 1. Test account connection
        if not test_account_connection(executor):
            logger.error("Account connection test failed!")
            return
        
        # 2. Test symbol information
        symbols_to_test = ['BTCUSD', 'ETHUSD', 'XAUUSD']
        if not test_symbol_info(executor, symbols_to_test):
            logger.error("Symbol information test failed!")
            return
        
        # 3. Test trading (with confirmation)
        print("\n=== Ready to Test Trading ===")
        print("This will open and close a test position!")
        print("Test trade details:")
        print("  Symbol: BTCUSD")
        print("  Size: 0.01 BTC (minimum lot)")
        print("  Actions: BUY then CLOSE")
        
        confirm = input("\nContinue with trade test? (y/n): ")
        
        if confirm.lower() == 'y':
            if test_market_order_and_close(executor, 'BTCUSD', 0.01):
                print("\n✅ Trading test completed successfully!")
            else:
                logger.error("Trading test failed!")
        else:
            print("\nTrading test skipped.")
        
        print("\n=== All Tests Complete ===")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)

if __name__ == "__main__":
    main()