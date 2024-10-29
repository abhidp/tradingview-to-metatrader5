import logging
import time
import json
import signal
import sys
from typing import Optional, Dict, Any
from src.utils.queue_handler import RedisQueue
from src.services.trade_executor import TradeExecutor
from src.utils.symbol_mapper import SymbolMapper

logger = logging.getLogger('MT5Worker')

class MT5Worker:
    def __init__(self):
        self.queue = RedisQueue()
        self.executor = TradeExecutor(SymbolMapper())
        self.running = True
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        print("\n🛑 Shutdown signal received...")
        self.running = False
        sys.exit(0)
    
    def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """Process a single trade."""
        try:
            execution_data = trade_data['execution_data']
            trade_type = trade_data['trade_type']
            
            logger.info(f"Processing {trade_type} trade for {execution_data['instrument']}")
            
            # Format trade request
            trade_request = {
                'instrument': execution_data['instrument'],
                'side': execution_data['side'],
                'qty': execution_data['qty'],
                'type': 'market',
                'position_id': execution_data.get('position_id'),
                'is_close': execution_data.get('is_close', False)
            }
            
            # Execute trade
            result = self.executor.execute_market_order(trade_request)
            
            if 'error' in result:
                logger.error(f"Trade execution failed: {result['error']}")
                self.queue.fail_trade(trade_data['id'], result['error'])
            else:
                logger.info(f"Trade executed successfully: {result}")
                self.queue.complete_trade(trade_data['id'], result)
                
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            if 'id' in trade_data:
                self.queue.fail_trade(trade_data['id'], str(e))
    
    def run(self):
        """Run the worker process."""
        print("\n🚀 MT5 Worker Started")
        print("Waiting for trades...\n")
        
        while self.running:
            try:
                if not self.running:
                    break
                    
                # Check queue
                trade = self.queue.get_trade()
                if trade:
                    trade_id, trade_data = trade
                    print(f"\n📥 Received trade: {trade_id}")
                    print(f"Trade details: {json.dumps(trade_data, indent=2)}")
                    
                    self.process_trade(trade_data)
                    
                    # Print queue status
                    status = self.queue.get_queue_status()
                    print(f"\nQueue Status: {status}")
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)
        
        print("\n✅ Worker stopped gracefully")
        sys.exit(0)
    
    def cleanup(self):
        """Clean up resources."""
        if hasattr(self.executor, 'cleanup'):
            self.executor.cleanup()