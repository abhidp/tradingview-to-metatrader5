import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal
from src.utils.database_handler import DatabaseHandler
from src.utils.queue_handler import RedisQueue

logger = logging.getLogger('TradeHandler')

class TradeHandler:
    def __init__(self):
        self.db = DatabaseHandler()
        self.queue = RedisQueue()
        self.pending_orders = {}
        
    def process_order(self, flow) -> None:
        """Process order request and response."""
        try:
            print("\n🔍 Processing order...")
            
            # Extract request data
            request_data = dict(flow.request.urlencoded_form)
            print(f"Request data: {json.dumps(request_data, indent=2)}")
            
            # Extract response data
            response_data = json.loads(flow.response.content.decode('utf-8'))
            print(f"Response data: {json.dumps(response_data, indent=2)}")
            
            # Create trade ID
            trade_id = f"TV_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{response_data['d']['orderId']}"
            
            # Prepare trade data
            trade_data = {
                'trade_id': trade_id,
                'order_id': response_data['d']['orderId'],
                'instrument': request_data['instrument'],
                'side': request_data['side'],
                'quantity': str(request_data['qty']),
                'type': request_data['type'],
                'ask_price': str(request_data['currentAsk']),
                'bid_price': str(request_data['currentBid']),
                'status': 'pending',
                'tv_request': request_data,
                'tv_response': response_data,
                'created_at': datetime.utcnow()
            }
            
            print(f"\n💾 Saving trade to database:")
            print(json.dumps(trade_data, indent=2))
            
            # Store in database
            try:
                self.db.save_trade(trade_data)
                print("✅ Trade saved to database successfully")
            except Exception as e:
                print(f"❌ Error saving to database: {e}")
                logger.error(f"Database error: {e}", exc_info=True)
                return
            
            # Add to pending orders
            self.pending_orders[response_data['d']['orderId']] = trade_id
            print(f"📝 Added to pending orders: {response_data['d']['orderId']}")
            
        except Exception as e:
            logger.error(f"Error processing order: {e}", exc_info=True)
            print(f"❌ Error: {e}")
    
    def process_execution(self, flow) -> None:
        """Process execution response."""
        try:
            print("\n🔍 Processing execution...")
            execution_data = json.loads(flow.response.content.decode('utf-8'))
            print(f"Execution data: {json.dumps(execution_data, indent=2)}")
            
            if execution_data.get('s') != 'ok' or 'd' not in execution_data:
                return
                
            executions = execution_data['d']
            for execution in executions:
                order_id = execution.get('orderId')
                if not order_id or order_id not in self.pending_orders:
                    continue
                    
                trade_id = self.pending_orders[order_id]
                print(f"\n📊 Found matching trade: {trade_id}")
                
                # Update trade with execution data
                update_data = {
                    'position_id': execution.get('positionId'),
                    'execution_price': str(execution.get('price', 0)),
                    'execution_data': execution,
                    'status': 'executed',
                    'executed_at': datetime.utcnow(),
                    'is_closed': execution.get('isClose', False)
                }
                
                print(f"💾 Updating trade in database:")
                print(json.dumps(update_data, indent=2))
                
                # Update database
                try:
                    self.db.update_trade(trade_id, update_data)
                    print("✅ Trade updated in database successfully")
                except Exception as e:
                    print(f"❌ Error updating database: {e}")
                    logger.error(f"Database error: {e}", exc_info=True)
                    return
                
                # Remove from pending orders
                del self.pending_orders[order_id]
                print(f"📝 Removed from pending orders: {order_id}")
                
        except Exception as e:
            logger.error(f"Error processing execution: {e}", exc_info=True)
            print(f"❌ Error: {e}")
    
    def handle_request(self, flow) -> None:
        """Route request to appropriate handler."""
        url = flow.request.pretty_url
        if '/orders?' in url and 'requestId=' in url:
            self.process_order(flow)
        elif '/executions?' in url and 'instrument=' in url:
            self.process_execution(flow)