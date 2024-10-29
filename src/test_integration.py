import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import time

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.trade_handler import TradeHandler
from src.core.trade_processor import TradeProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('IntegrationTest')

def simulate_tradingview_request():
    """Simulate a TradingView trade request."""
    return {
        "currentAsk": "68905.36",
        "currentBid": "68890.36",
        "instrument": "BTCUSD",
        "qty": "0.01",
        "side": "buy",
        "type": "market"
    }

class MockFlow:
    """Mock mitmproxy flow for testing."""
    def __init__(self, form_data):
        self.request = type('Request', (), {
            'urlencoded_form': form_data,
            'hash': 'test_hash'
        })
        self.response = type('Response', (), {
            'content': b'{"s":"ok","d":{"orderId":"test_order"}}'
        })

def main():
    try:
        print("\n=== Testing Trade Flow Integration ===")
        
        # Initialize components
        handler = TradeHandler()
        
        # Create mock request
        trade_request = simulate_tradingview_request()
        mock_flow = MockFlow(trade_request)
        
        print("\nSimulated TradingView Request:")
        for key, value in trade_request.items():
            print(f"{key}: {value}")
        
        # Process trade
        print("\nProcessing trade...")
        handler.process_trade(mock_flow)
        
        print("\n=== Test Complete ===")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()