import logging
import json
from datetime import datetime
from typing import Dict, Any
from src.utils.database_handler import DatabaseHandler
from src.utils.queue_handler import RedisQueue

logger = logging.getLogger('TradeHandler')

class TradeHandler:
    def __init__(self):
        self.db = DatabaseHandler()
        self.queue = RedisQueue()
        self.pending_orders = {}  # Track order->execution mapping
    
    def process_order(self, request_data: Dict[str, Any], response_data: Dict[str, Any]) -> None:
        """Process new order from TradingView."""
        try:
            trade_id = f"TV_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{response_data['d']['orderId']}"
            
            trade_data = {
                'trade_id': trade_id,
                'order_id': response_data['d']['orderId'],
                'instrument': request_data['instrument'],
                'side': request_data['side'],
                'quantity': request_data['qty'],
                'type': request_data['type'],
                'ask_price': request_data['currentAsk'],
                'bid_price': request_data['currentBid'],
                'status': 'pending',
                'tv_request': request_data,
                'tv_response': response_data,
                'created_at': datetime.utcnow()
            }
            
            print("\n💾 Storing trade in database...")
            self.db.save_trade(trade_data)
            print("✅ Trade stored successfully")
            
            # Track order for execution matching
            self.pending_orders[response_data['d']['orderId']] = trade_id
            
        except Exception as e:
            logger.error(f"Error processing order: {e}")
            print(f"❌ Error processing order: {e}")
    
    def process_execution(self, execution_data: Dict[str, Any]) -> None:
        """Process execution update from TradingView."""
        try:
            executions = execution_data.get('d', [])
            for execution in executions:
                order_id = execution.get('orderId')
                if order_id and order_id in self.pending_orders:
                    trade_id = self.pending_orders[order_id]
                    
                    # Get existing trade to get MT5 ticket if available
                    trade = self.db.get_trade(trade_id)
                    mt5_ticket = trade.get('mt5_ticket') if trade else None
                    
                    # First update database with execution data
                    update_data = {
                        'position_id': execution.get('positionId'),
                        'execution_price': execution.get('price'),
                        'execution_data': execution,
                        'executed_at': datetime.utcnow(),
                        'is_closed': execution.get('isClose', False)
                    }
                    
                    self.db.update_trade_status(trade_id, 'executed', update_data)
                    
                    # Then push to queue for MT5
                    queue_data = {
                        'trade_id': trade_id,
                        'execution_data': execution,
                        'mt5_ticket': mt5_ticket,
                        'instrument': execution.get('instrument'),  # Add instrument
                        'side': execution.get('side'),             # Add side
                        'qty': execution.get('qty')                # Add quantity
                    }
                    print(f"\n📤 Pushing trade to queue...")
                    self.queue.push_trade(queue_data)
                    
                    # Remove from pending orders
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            logger.error(f"Error processing execution: {e}")
            print(f"❌ Error processing execution: {e}")               
    
    def process_position_close(self, position_id: str) -> None:
        """Process position close request from TradingView."""
        try:
            print(f"\n🔴 Processing position close: {position_id}")
            
            # Find trade in database by position ID
            trade = self.db.get_trade_by_position(position_id)
            if not trade:
                print(f"❌ No trade found for position {position_id}")
                return
            
            print("\n📋 Trade data found:")
            print(json.dumps(trade, indent=2))
            
            mt5_ticket = trade.get('mt5_ticket')
            if not mt5_ticket:
                print(f"❌ No MT5 ticket found for trade {trade['trade_id']}")
                return
            
            # Prepare close data with ALL necessary fields
            close_data = {
                'trade_id': trade['trade_id'],
                'mt5_ticket': mt5_ticket,
                'instrument': trade['instrument'],  # Add instrument
                'type': 'market',                  # Add type
                'qty': trade['quantity'],          # Add quantity
                'side': 'sell' if trade['side'] == 'buy' else 'buy',  # Add reversed side
                'execution_data': {
                    'instrument': trade['instrument'],
                    'positionId': position_id,
                    'qty': trade['quantity'],
                    'side': 'sell' if trade['side'] == 'buy' else 'buy',
                    'isClose': True
                }
            }
            
            print(f"\n📤 Pushing close request:")
            print(f"MT5 Ticket: {mt5_ticket}")
            print(f"Instrument: {trade['instrument']}")
            print(f"Side: {close_data['side']}")
            print(f"Quantity: {trade['quantity']}")
            
            self.queue.push_trade(close_data)
            
            # Update trade status
            self.db.update_trade_status(trade['trade_id'], 'closing', {
                'close_requested_at': datetime.utcnow().isoformat()
            })
            
            print("✅ Close request processed")
            
        except Exception as e:
            logger.error(f"Error processing position close: {e}")
            print(f"❌ Error processing position close: {e}")