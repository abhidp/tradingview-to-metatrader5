import logging
import time
from typing import Dict, Any, Set
from datetime import datetime
import MetaTrader5 as mt5
from src.core.interceptor import GLOBAL_TOKEN_MANAGER
from src.utils.queue_handler import RedisQueue
from src.services.mt5_service import MT5Service
from src.services.tradingview_service import TradingViewService
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
        self.tv_service = TradingViewService(
            token_manager=GLOBAL_TOKEN_MANAGER
        )
        self.running = True
        self.open_positions: Set[str] = set()

    def check_mt5_positions(self) -> None:
        """Monitor MT5 positions for manual closes."""
        try:
            if not self.mt5.initialize():
                return

            current_positions = mt5.positions_get()
            if current_positions is None:
                return

            current_position_tickets = {str(pos.ticket) for pos in current_positions}

            # Check for closed positions
            for ticket in self.open_positions.copy():
                if ticket not in current_position_tickets:
                    self.handle_mt5_close(ticket)
                    self.open_positions.remove(ticket)

            self.open_positions = current_position_tickets

        except Exception as e:
            logger.error(f"Error checking positions: {e}")

    def handle_mt5_close(self, mt5_ticket: str) -> None:
        """Handle position closed in MT5."""
        try:            
            trade = self.db.get_trade_by_mt5_ticket(mt5_ticket)
            if not trade:
                return

            if trade.get('is_closed'):
                return

            position_id = trade.get('position_id')
            if not position_id:
                logger.error(f"No position ID for trade {trade['trade_id']}")
                return

            # Close in TradingView
            result = self.tv_service.close_position(position_id)
            if 'error' in result:
                logger.error(f"Failed to close TV position: {result['error']}")
                return

            print(f"✅ Position closed: {trade['instrument']} {trade['quantity']}")

            self.db.update_trade_status(trade['trade_id'], 'closed', {
                'is_closed': True,
                'closed_at': datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Error handling MT5 close: {e}")
            if 'trade' in locals() and trade:
                self.db.update_trade_status(trade['trade_id'], 'failed', {
                    'error_message': str(e)
                })

    def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """Process a single trade."""
        try:
            trade_id = trade_data['trade_id']
            # Get start time from Redis
            start_time = int(self.queue.redis.hget('trade_times', trade_id) or 0)
            if not start_time:
                logger.warning(f"No start time found for trade {trade_id}")

            # Execute or close based on isClose flag
            if trade_data.get('execution_data', {}).get('isClose', False):
                logger.info("Processing close request")
                result = self.mt5.close_position(trade_data)
            else:
                logger.info("Processing new position")
                result = self.mt5.execute_market_order(trade_data)
            
            # Calculate execution time
            end_time = int(time.time() * 1000)
            execution_time = end_time - start_time if start_time else None
            
            if execution_time:
                print(f"⚡ Position executed in {execution_time}ms")

            if 'error' in result:
                logger.error(f"Trade execution failed: {result['error']}")
                self.db.update_trade_status(trade_data['trade_id'], 'failed', {
                    'error_message': result['error'],
                    'mt5_response': result
                })
                return
            
            # Update database
            status = 'closed' if trade_data.get('execution_data', {}).get('isClose') else 'completed'
            self.db.update_trade_status(trade_data['trade_id'], status, {
                'mt5_ticket': result['mt5_ticket'],
                'mt5_position': result['mt5_position'],
                'mt5_response': result,
                'execution_time_ms': execution_time
            })

            # Clean up timing data
            self.queue.redis.hdel('trade_times', trade_id)
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            if 'trade_id' in trade_data:
                self.db.update_trade_status(trade_data['trade_id'], 'failed', {
                    'error_message': str(e)
                })

    def run(self):
        """Run the worker process."""
        print("\n🚀 MT5 Worker Started")
        print("Waiting for trades...\n")
        
        while self.running:
            try:
                # Process trades from queue
                trade = self.queue.get_trade()
                if trade:
                    trade_id, trade_data = trade
                    self.process_trade(trade_data)

                # Check for MT5 position changes
                self.check_mt5_positions()
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nShutdown requested...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up...")
        self.mt5.cleanup()