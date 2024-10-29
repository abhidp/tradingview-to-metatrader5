from mitmproxy import ctx, http
import logging
import json
from datetime import datetime
from src.utils.database_handler import DatabaseHandler
from src.utils.queue_handler import RedisQueue

# Disable mitmproxy's default logging
ctx.log.silent = True
ctx.options.flow_detail = 0

class TradingViewInterceptor:
    def __init__(self):
        self.base_path = "icmarkets.tv.ctrader.com/accounts/40807470"
        self.db = DatabaseHandler()
        self.queue = RedisQueue()
        self.pending_orders = {}
        print("\n🚀 Trade interceptor initialized")
        print("Watching for trades...\n")

    def should_log_request(self, flow: http.HTTPFlow) -> bool:
        """Strictly check if we should log this request."""
        url = flow.request.pretty_url
        
        # Must be our base path
        if self.base_path not in url:
            return False
            
        # Must be one of our two target endpoints
        if '/orders?locale=' in url and 'requestId=' in url:
            return True
        if '/executions?locale=' in url and 'instrument=' in url:
            return True
            
        return False

    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        if not self.should_log_request(flow):
            return
            
        print(f"\n{'='*50}")
        print(f"📡 Intercepted Request: {flow.request.pretty_url}")
        
        if flow.request.method == "POST":
            if flow.request.urlencoded_form:
                print("\n📤 Trade Data:")
                print(json.dumps(dict(flow.request.urlencoded_form), indent=2))

    def response(self, flow: http.HTTPFlow) -> None:
        """Handle responses."""
        if not self.should_log_request(flow):
            return
            
        if flow.response and flow.response.content:
            try:
                response_data = json.loads(flow.response.content.decode('utf-8'))
                print("\n📥 Response Data:")
                print(json.dumps(response_data, indent=2))
                print(f"{'='*50}\n")
                
                # Store order in database
                if '/orders?locale=' in flow.request.pretty_url and flow.request.method == "POST":
                    try:
                        request_data = dict(flow.request.urlencoded_form)
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
                        print(f"❌ Error storing trade: {e}")
                
                # Update with execution data
                elif '/executions?locale=' in flow.request.pretty_url:
                    try:
                        executions = response_data.get('d', [])
                        for execution in executions:
                            order_id = execution.get('orderId')
                            if order_id in self.pending_orders:
                                trade_id = self.pending_orders[order_id]
                                
                                update_data = {
                                    'position_id': execution.get('positionId'),
                                    'execution_price': execution.get('price'),
                                    'status': 'executed',
                                    'execution_data': execution,
                                    'executed_at': datetime.utcnow(),
                                    'is_closed': execution.get('isClose', False)
                                }
                                
                                print("\n💾 Updating trade execution data...")
                                self.db.update_trade(trade_id, update_data)
                                print("✅ Trade updated successfully")
                                
                                # Push to Redis queue for MT5
                                self.queue.push_trade({
                                    'trade_id': trade_id,
                                    'execution_data': execution
                                })
                                print("📤 Trade pushed to queue")
                                
                                # Remove from pending orders
                                del self.pending_orders[order_id]
                                
                    except Exception as e:
                        print(f"❌ Error updating trade: {e}")
                
            except Exception as e:
                print(f"❌ Error processing response: {e}")

addons = [TradingViewInterceptor()]