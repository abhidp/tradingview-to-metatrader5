import logging
import time
import threading
import signal
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
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MT5Worker, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Skip if already initialized
        if self._initialized:
            return
            
        self.queue = RedisQueue()
        self.db = DatabaseHandler()
        self.mt5 = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
        # Initialize TradingView service without printing status
        self.tv_service = TradingViewService(
            token_manager=GLOBAL_TOKEN_MANAGER,
            print_status=False  # Explicitly disable status printing for worker
        )
        
        self._stop_event = threading.Event()
        self.open_positions: Set[str] = set()
        self._position_check_thread: threading.Thread | None = None
        
        # Print worker status
        print("\n🚀 MT5 Worker Started")
        print("Waiting for trades...\n")
        
        self._initialized = True

    def handle_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """Handle messages from Redis channels."""
        try:
            if self._stop_event.is_set():
                return
                
            if msg_type == 'trade':
                self.process_trade(data['data'])
            elif msg_type == 'status':
                print(f"📡 Status: {data['message']}")
            elif msg_type == 'error':
                logger.error(f"Queue error: {data['error']}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def process_trade(self, trade_data: Dict[str, Any]) -> None:
        """Process a single trade."""
        try:
            trade_id = trade_data['trade_id']
            start_time = int(time.time() * 1000)
            
            print(f"\n📥 Processing trade: {trade_id}")

            if trade_data.get('execution_data', {}).get('isClose', False):
                logger.info("Closing position")
                result = self.mt5.close_position(trade_data)
            else:
                logger.info("Opening position")
                result = self.mt5.execute_market_order(trade_data)
            
            end_time = int(time.time() * 1000)
            execution_time = end_time - start_time
            
            if 'error' in result:
                logger.error(f"Trade execution failed: {result['error']}")
                self.db.update_trade_status(trade_id, 'failed', {
                    'error_message': result['error'],
                    'mt5_response': result,
                    'execution_time_ms': execution_time
                })
                return
            
            status = 'closed' if trade_data.get('execution_data', {}).get('isClose') else 'completed'
            self.db.update_trade_status(trade_id, status, {
                'mt5_ticket': result['mt5_ticket'],
                'mt5_position': result['mt5_position'],
                'mt5_response': result,
                'execution_time_ms': execution_time
            })
            
            print(f"⚡ Position executed in {execution_time}ms")
            # print(f"✅ Trade {status}: {result['symbol']} {result['side']} x {result['volume']}")
            if result.get('take_profit') or result.get('stop_loss'):
                print(f"   TP: {result.get('take_profit')} | SL: {result.get('stop_loss')}")
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            if 'trade_id' in trade_data:
                self.db.update_trade_status(trade_data['trade_id'], 'failed', {
                    'error_message': str(e)
                })

    def check_mt5_positions(self) -> None:
        """Monitor MT5 positions for manual closes."""
        logger.info("Position monitoring started")
        while not self._stop_event.is_set():
            try:
                if not self.mt5.initialize():
                    time.sleep(1)
                    continue

                current_positions = mt5.positions_get()
                if current_positions is None:
                    time.sleep(1)
                    continue

                current_position_tickets = {str(pos.ticket) for pos in current_positions}

                for ticket in self.open_positions.copy():
                    if ticket not in current_position_tickets:
                        self.handle_mt5_close(ticket)
                        self.open_positions.remove(ticket)

                self.open_positions = current_position_tickets
                time.sleep(1)

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error checking positions: {e}")
                time.sleep(1)

        logger.info("Position monitoring stopped")

    def handle_mt5_close(self, mt5_ticket: str) -> None:
        """Handle position closed in MT5."""
        try:            
            trade = self.db.get_trade_by_mt5_ticket(mt5_ticket)
            if not trade or trade.get('is_closed'):
                return

            position_id = trade.get('position_id')
            if not position_id:
                logger.error(f"No position ID for trade {trade['trade_id']}")
                return

            result = self.tv_service.close_position(position_id)
            if 'error' in result:
                logger.error(f"Failed to close TV position: {result['error']}")
                return

            print(f"✅ Position closed in TV: {trade['instrument']} {trade['quantity']}")

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

    def run(self):
        """Run the worker service."""
        try:
            # Start position checking thread
            self._position_check_thread = threading.Thread(target=self.check_mt5_positions)
            self._position_check_thread.daemon = True
            self._position_check_thread.start()
            
            # Subscribe to Redis queue in main thread
            logger.info("Starting Redis subscription...")
            self.queue.subscribe(self.handle_message)
            
        except KeyboardInterrupt:
            print("\nShutdown requested...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self, '_cleanup_done'):
            return
            
        logger.info("Cleaning up...")
        self._stop_event.set()
        
        # Stop Redis subscription
        try:
            self.queue.close()
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")

        # Wait for position check thread
        if self._position_check_thread and self._position_check_thread.is_alive():
            logger.info("Waiting for position check thread to stop...")
            self._position_check_thread.join(timeout=2.0)
        
        # Cleanup MT5
        try:
            self.mt5.cleanup()
        except Exception as e:
            logger.error(f"Error during MT5 cleanup: {e}")
        
        self._cleanup_done = True
        logger.info("Cleanup completed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()