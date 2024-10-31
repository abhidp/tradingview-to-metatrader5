import logging
import time
import json
from typing import Dict, Any
from datetime import datetime
from src.utils.queue_handler import RedisQueue
from src.services.mt5_service import MT5Service
from src.utils.database_handler import DatabaseHandler
from src.config.mt5_config import MT5_CONFIG

logger = logging.getLogger('MT5Worker')

class MT5Worker:
    def __init__(self):
        self.queue = RedisQueue()
        self.db = DatabaseHandler()
        self.mt5 = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
        self.running = True

    def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """Process a single trade."""
        try:
            execution = trade_data['execution_data']
            trade_id = trade_data['trade_id']
            mt5_ticket = trade_data.get('mt5_ticket')
            
            print("\nProcessing trade data:")
            print(f"Trade ID: {trade_id}")
            print(f"MT5 Ticket: {mt5_ticket}")
            print(f"Is Close: {execution.get('isClose', False)}")
            
            # If this is a close request
            if execution.get('isClose', False):
                if not mt5_ticket:
                    logger.error(f"Cannot close trade without MT5 ticket")
                    return
                
                logger.info(f"Closing position with MT5 ticket: {mt5_ticket}")
                result = self.mt5.close_position(trade_data)
            else:
                # New trade
                logger.info("Opening new position")
                mt5_request = {
                    'trade_id': trade_id,
                    'instrument': execution['instrument'],
                    'side': execution['side'],
                    'qty': execution['qty'],
                    'type': 'market'
                }
                result = self.mt5.execute_market_order(mt5_request)
            
            if 'error' in result:
                logger.error(f"Trade execution failed: {result['error']}")
                self.db.update_trade_status(trade_id, 'failed', {
                    'error_message': result['error'],
                    'mt5_response': result
                })
                return
            
            # Update database with MT5 ticket
            status = 'closed' if execution.get('isClose', False) else 'completed'
            update_data = {
                'status': status,
                'mt5_ticket': result['mt5_ticket'],
                'mt5_position': result['mt5_position'],  # This should match the ticket for new trades
                'mt5_response': result
            }
            
            # Add closing-specific data
            if status == 'closed':
                update_data.update({
                    'closed_at': datetime.utcnow().isoformat(),
                    'is_closed': True
                })
            
            logger.info(f"Updating trade {trade_id} with MT5 data")
            self.db.update_trade_status(trade_id, status, update_data)
            
            # Log success
            logger.info(f"Trade {trade_id} {status} successfully on MT5")
            print(f"\n✅ MT5 Trade {'Closed' if status == 'closed' else 'Executed'}:")
            print(f"Symbol: {result['symbol']}")
            print(f"Side: {result['side']}")
            print(f"Volume: {result['volume']}")
            print(f"Price: {result['price']}")
            print(f"Ticket: {result['mt5_ticket']}")
            if status == 'closed':
                print(f"Closed Position: {result.get('closed_position')}")
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            self.db.update_trade_status(trade_id, 'failed', {
                'error_message': str(e)
            })

    def run(self):
        """Run the worker process."""
        print("\n🚀 MT5 Worker Started")
        print("Waiting for trades...\n")
        
        while self.running:
            try:
                # Get trade from queue
                trade = self.queue.get_trade()
                if trade:
                    trade_id, trade_data = trade
                    print(f"\n📥 Received trade: {trade_id}")
                    self.process_trade(trade_data)
                
                time.sleep(0.1)  # Small delay to prevent CPU overload
                
            except KeyboardInterrupt:
                print("\nShutdown requested...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)  # Longer delay on error
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up...")
        self.mt5.cleanup()