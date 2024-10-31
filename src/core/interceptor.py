from mitmproxy import ctx, http
import json
from datetime import datetime
from src.core.trade_handler import TradeHandler

# Disable mitmproxy's default logging
ctx.log.silent = True
ctx.options.flow_detail = 0

class TradingViewInterceptor:
    def __init__(self):
        self.base_path = "icmarkets.tv.ctrader.com/accounts/40807470"
        self.trade_handler = TradeHandler()  # Use TradeHandler instead of direct DB and Queue
        print("\n🚀 Trade interceptor initialized")
        print("Watching for trades...\n")

    def should_log_request(self, flow: http.HTTPFlow) -> bool:
        """Strictly check if we should log this request."""
        url = flow.request.pretty_url
        
        if self.base_path not in url:
            return False
        
        # Match orders, executions, and position closures
        if '/orders?locale=' in url and 'requestId=' in url:
            return True
        if '/executions?locale=' in url and 'instrument=' in url:
            return True
        if '/positions/' in url and flow.request.method == "DELETE":
            return True
            
        return False

    def handle_order(self, flow: http.HTTPFlow, response_data: dict) -> None:
        """Handle new order request."""
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
            print(f"❌ Error handling order: {e}")

    def handle_execution(self, flow: http.HTTPFlow, response_data: dict) -> None:
        """Handle execution update."""
        try:
            executions = response_data.get('d', [])
            for execution in executions:
                order_id = execution.get('orderId')
                if order_id in self.pending_orders:
                    trade_id = self.pending_orders[order_id]
                    
                    update_data = {
                        'position_id': execution.get('positionId'),
                        'execution_price': execution.get('price'),
                        'execution_data': execution,
                        'executed_at': datetime.utcnow(),
                        'is_closed': execution.get('isClose', False)
                    }
                    
                    # Update database and push to queue
                    self.db.update_trade_status(trade_id, 'executed', update_data)
                    
                    # Include both TV position ID and MT5 ticket
                    self.queue.push_trade({
                        'trade_id': trade_id,
                        'execution_data': execution,
                        'mt5_ticket': update_data.get('mt5_ticket')  # Include MT5 ticket
                    })
        except Exception as e:
            print(f"❌ Error handling execution: {e}")

    def handle_position_close(self, flow: http.HTTPFlow) -> None:
        """Handle position close request."""
        try:
            # Extract position ID from URL
            url_parts = flow.request.pretty_url.split('/')
            position_id = url_parts[-1].split('?')[0]
            
            print(f"\n🔴 Position close request detected:")
            print(f"Position ID: {position_id}")
            
            # Find trade in database by position ID
            trade = self.db.get_trade_by_position(position_id)
            if not trade:
                print(f"❌ No trade found for position {position_id}")
                return
                
            # Prepare close data with MT5 ticket
            close_data = {
                'trade_id': trade['trade_id'],
                'execution_data': {
                    'instrument': trade['instrument'],
                    'positionId': position_id,
                    'qty': trade['quantity'],
                    'side': 'sell' if trade['side'] == 'buy' else 'buy',  # Reverse side for closing
                    'isClose': True
                },
                'mt5_ticket': trade['mt5_ticket']  # Add MT5 ticket for closing
            }
            
            print("📤 Pushing close request to queue")
            self.queue.push_trade(close_data)
            
            print(f"🎫 Using MT5 ticket: {trade['mt5_ticket']} for closing")
            
            # Update trade status
            self.db.update_trade_status(trade['trade_id'], 'closing', {
                'close_requested_at': datetime.utcnow().isoformat()
            })
            
            print("✅ Close request processed")
            
        except Exception as e:
            print(f"❌ Error processing close request: {e}")

    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        if not self.should_log_request(flow):
            return
            
        print(f"\n{'='*50}")
        print(f"📡 Intercepted Request: {flow.request.method} {flow.request.pretty_url}")
        
        if flow.request.method == "POST" and flow.request.urlencoded_form:
            print("\n📤 Trade Data:")
            print(json.dumps(dict(flow.request.urlencoded_form), indent=2))
        elif flow.request.method == "DELETE":
            # Extract position ID from URL
            url_parts = flow.request.pretty_url.split('/')
            position_id = url_parts[-1].split('?')[0]
            self.trade_handler.process_position_close(position_id)


    def response(self, flow: http.HTTPFlow) -> None:
        """Handle responses."""
        if not self.should_log_request(flow):
            return
            
        if flow.response and flow.response.content:
            try:
                response_data = json.loads(flow.response.content.decode('utf-8'))
                # print("\n📥 Response Data:")
                # print(json.dumps(response_data, indent=2))
                # print(f"{'='*50}\n")
                
                # Handle order and execution responses
                if '/orders?' in flow.request.pretty_url and flow.request.method == "POST":
                    self.trade_handler.process_order(
                        dict(flow.request.urlencoded_form), 
                        response_data
                    )
                elif '/executions?' in flow.request.pretty_url:
                    self.trade_handler.process_execution(response_data)
                    
            except Exception as e:
                print(f"❌ Error processing response: {e}")

addons = [TradingViewInterceptor()]