import logging
import time
import json
from typing import Dict, Any, Set
from datetime import datetime
import MetaTrader5 as mt5
from src.core.interceptor import GLOBAL_TOKEN_MANAGER
from src.utils.queue_handler import RedisQueue
from src.services.mt5_service import MT5Service
from src.services.tradingview_service import TradingViewService
from src.utils.token_manager import TokenManager
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
            account_id="40807470",  # Move to config
            token_manager=GLOBAL_TOKEN_MANAGER  # Use global token manager
        )
        self.running = True
        self.open_positions: Set[str] = set()  # Track open positions

    def check_mt5_positions(self) -> None:
        """Monitor MT5 positions for manual closes."""
        try:
            if not self.mt5.initialize():
                return

            # Get current positions
            current_positions = mt5.positions_get()
            if current_positions is None:
                return

            # Convert to set of ticket numbers
            current_position_tickets = {str(pos.ticket) for pos in current_positions}

            # Check for positions that were open but now are closed
            for ticket in self.open_positions.copy():
                if ticket not in current_position_tickets:
                    self.handle_mt5_close(ticket)
                    self.open_positions.remove(ticket)

            # Update tracked positions
            self.open_positions = current_position_tickets

        except Exception as e:
            logger.error(f"Error checking MT5 positions: {e}")

    def handle_mt5_close(self, mt5_ticket: str) -> None:
        """Handle position closed in MT5."""
        try:            
            # Find trade in database
            trade = self.db.get_trade_by_mt5_ticket(mt5_ticket)
            if not trade:
                print(f"❌ No trade found for MT5 ticket {mt5_ticket}")
                return

            # Check if already closed
            if trade.get('is_closed'):
                print(f"ℹ️ Trade {trade['trade_id']} already marked as closed")
                return

            position_id = trade.get('position_id')
            if not position_id:
                print(f"❌ No position ID found for trade {trade['trade_id']}")
                return

            # Close in TradingView
            result = self.tv_service.close_position(position_id)
            if 'error' in result:
                print(f"❌ Failed to close TradingView position: {result['error']}")
                return

            print("✅ Position closed in TradingView")

            # Update database
            closed_time = datetime.utcnow()
            self.db.update_trade_status(trade['trade_id'], 'closed', {
                'is_closed': True,
                'closed_at': closed_time.isoformat()
            })
            print("✅ Database updated")

        except Exception as e:
            logger.error(f"Error handling MT5 close: {e}")
            print(f"❌ Error: {e}")
            # Update database with error state
            if 'trade' in locals() and trade:
                self.db.update_trade_status(trade['trade_id'], 'failed', {
                    'error_message': str(e)
                })

    def close_positions(self, mt5_ticket: str) -> None:
        """Close positions on both platforms."""
        try:
            print("\n🔄 Starting position close process...")
            print(f"MT5 Ticket to close: {mt5_ticket}")
            
            # Find trade in database
            print("\n1️⃣ Looking up trade in database...")
            trade = self.db.get_trade_by_mt5_ticket(mt5_ticket)
            if not trade:
                logger.error(f"No trade found for MT5 ticket {mt5_ticket}")
                print("❌ No trade found in database")
                return
            
            print("\n📊 Found trade details:")
            print(f"Trade ID: {trade.get('trade_id')}")
            print(f"Position ID: {trade.get('position_id')}")
            print(f"Instrument: {trade.get('instrument')}")
            print(f"Side: {trade.get('side')}")
            print(f"Quantity: {trade.get('quantity')}")
            print(f"Status: {trade.get('status')}")
            
            position_id = trade.get('position_id')
            if not position_id:
                logger.error(f"No position ID found for trade {trade['trade_id']}")
                print("❌ No TradingView position ID found")
                return
            
            # Show token status
            print("\n2️⃣ Checking TradingView authorization...")
            token = self.tv_service.token_manager.get_token()
            if not token:
                print("❌ No authorization token available")
                logger.error("No TradingView authorization token available")
                return
            print("✅ Authorization token found")
            
            # Close on TradingView
            print(f"\n3️⃣ Sending close request to TradingView for position {position_id}...")
            result = self.tv_service.close_position(position_id)
            
            print("\n📡 TradingView API Response:")
            print(f"Result: {result}")
            
            if 'error' in result:
                logger.error(f"Failed to close TradingView position: {result['error']}")
                print(f"❌ Close request failed: {result['error']}")
                return
                
            logger.info(f"Position {position_id} closed on TradingView")
            print("✅ Position closed successfully on TradingView")
            
            # Update database
            print("\n4️⃣ Updating database...")
            self.db.update_trade_status(trade['trade_id'], 'closing', {
                'close_requested_at': datetime.utcnow().isoformat(),
                'is_closed': True
            })
            print("✅ Database updated")
            
            print("\n✅ Position close process completed successfully!")
            
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
            print(f"\n❌ Error during close process: {e}")
            
            # Optionally update database with error
            if 'trade' in locals() and trade:
                print("\n🔄 Recording error in database...")
                self.db.update_trade_status(trade['trade_id'], 'failed', {
                    'error_message': f"Error closing position: {str(e)}"
                })
                print("✅ Error recorded in database")

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
            
            # logger.info(f"Updating trade {trade_id} with MT5 data")
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
                # Check for trades from queue
                trade = self.queue.get_trade()
                if trade:
                    trade_id, trade_data = trade
                    print(f"\n📥 Received trade: {trade_id}")
                    self.process_trade(trade_data)

                # Check for MT5 position changes
                self.check_mt5_positions()
                
                time.sleep(1)  # Reduced from 0.1 to check positions less frequently
                
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