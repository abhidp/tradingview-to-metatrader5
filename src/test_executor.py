import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
from src.services.trade_executor import TradeExecutor
from src.utils.symbol_mapper import SymbolMapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Create executor
    executor = TradeExecutor(SymbolMapper())
    
    # 1. Verify account
    print("\nChecking account status...")
    account_status = executor.verify_account()
    print(f"Account status: {account_status}")
    
    # 2. Check symbol info
    print("\nChecking symbol info...")
    symbols = ['BTCUSD', 'ETHUSD', 'XAUUSD']
    for symbol in symbols:
        info = executor.get_symbol_info(symbol)
        print(f"\n{symbol} info:")
        print(f"MT5 Symbol: {info.get('symbol')}")
        print(f"Bid: {info.get('bid')}")
        print(f"Ask: {info.get('ask')}")
        print(f"Min Lot: {info.get('min_lot')}")
        print(f"Lot Step: {info.get('lot_step')}")
    
    # 3. Test market order (with minimal size)
    print("\nTesting market order...")
    test_trade = {
        "instrument": "BTCUSD",
        "side": "buy",
        "qty": 0.01,
        "type": "market",
        "requestId": "test_trade_1"
    }
    
    # Ask for confirmation before placing trade
    confirm = input(f"\nReady to place test trade: {test_trade}\nContinue? (y/n): ")
    if confirm.lower() == 'y':
        result = executor.execute_market_order(test_trade)
        print(f"\nTrade result: {result}")
    else:
        print("Test trade cancelled")

if __name__ == "__main__":
    main()