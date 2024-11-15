
import asyncio
import json
import os

from dotenv import load_dotenv

from mitmproxy import http
from src.core.trade_handler import TradeHandler
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER, TokenManager

load_dotenv()
TV_BROKER_URL = os.getenv('TV_BROKER_URL')
TV_ACCOUNT_ID = os.getenv('TV_ACCOUNT_ID')

# Create a global token manager instance
GLOBAL_TOKEN_MANAGER = TokenManager()

class TradingViewInterceptor:
    """Intercepts and handles TradingView requests."""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TradingViewInterceptor, cls).__new__(cls)
        return cls._instance


    def __init__(self):
        if not self._initialized:  # Only initialize once
            self.base_path = f"{TV_BROKER_URL}/accounts/{TV_ACCOUNT_ID}"
            self.trade_handler = TradeHandler()
            self.token_manager = GLOBAL_TOKEN_MANAGER

            broker_url = os.getenv('TV_BROKER_URL', 'Unknown Broker')
            account_id = os.getenv('TV_ACCOUNT_ID', 'Unknown Account')

            print("\n🚀 Trade interceptor initialized")
            print("👀 Watching for trades...\n")
            print(f"✅ TradingView Connected: {account_id} ({broker_url})")

            self._initialized = True




    def should_log_request(self, flow: http.HTTPFlow) -> bool:
        """Strictly check if we should log this request."""
        url = flow.request.pretty_url
        
        if self.base_path not in url:
            return False
        
        # Match orders, executions, position closures, and position updates
        if '/orders?locale=' in url and 'requestId=' in url:
            return True
        if '/executions?locale=' in url and 'instrument=' in url:
            return True
        if '/positions/' in url:
            return flow.request.method in ["DELETE", "PUT"]
        if '.TP.' in url or '.SL.' in url:
            return flow.request.method == "DELETE"   
            
        return False

    async def async_process_order(self, request_data: dict, response_data: dict) -> None:
        """Asynchronously process order."""
        await self.trade_handler.process_order(request_data, response_data)

    async def async_process_position_update(self, position_id: str, update_data: dict) -> None:
        """Asynchronously process position update."""
        await self.trade_handler.process_position_update(position_id, update_data)

    async def async_process_position_close(self, position_id: str, close_data: dict[str, any] = None) -> None:
        """Asynchronously process position close."""
        await self.trade_handler.process_position_close(position_id, close_data)

    async def async_process_execution(self, response_data: dict) -> None:
        """Asynchronously process execution."""
        await self.trade_handler.process_execution(response_data)

    async def async_process_tpsl_delete(self, order_id: str, order_type: str) -> None:
        """Process TP/SL deletion request."""
        await self.trade_handler.process_tpsl_delete(order_id, order_type)

    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        if self.base_path in flow.request.pretty_url:
            auth_header = flow.request.headers.get('authorization')
            if auth_header:
                self.token_manager.update_token(auth_header)
        
        if not self.should_log_request(flow):
            return
        
        if flow.request.method == "DELETE":
            url = flow.request.pretty_url
        
            # Handle TP/SL deletion
            if '.TP.' in url or '.SL.' in url:
                # Extract order ID from the URL
                # Format: orders/orderId.TP|SL.timestamp
                parts = url.split('/')[-1].split('.')
                order_id = parts[0]  # This is what we need
                level_type = parts[1]  # 'TP' or 'SL'
                
                print(f"\n💱 Processing {level_type} deletion for OrderID#: {order_id}")
                asyncio.create_task(
                    self.async_process_tpsl_delete(order_id, level_type)
                )
            else:
                # Only process position close for non-TP/SL deletions
                url_parts = flow.request.pretty_url.split('/')
                position_id = url_parts[-1].split('?')[0]
                
                # Get close data if exists
                close_data = {}
                if flow.request.urlencoded_form:
                    close_data = dict(flow.request.urlencoded_form)
                
                # Create and run the coroutine in the event loop
                asyncio.create_task(
                    self.async_process_position_close(position_id, close_data)
                )

    def response(self, flow: http.HTTPFlow) -> None:
        """Handle responses."""
        if not self.should_log_request(flow):
            return
            
        if flow.response and flow.response.content:
            try:
                response_data = json.loads(flow.response.content.decode('utf-8'))
                
                if '/positions/' in flow.request.pretty_url:
                    if flow.request.method == "PUT":
                        # Extract position ID from URL
                        url_parts = flow.request.pretty_url.split('/')
                        position_id = url_parts[-1].split('?')[0]
                        
                        # Get update data and merge with response
                        update_data = dict(flow.request.urlencoded_form)
                        if 's' in response_data and response_data['s'] == 'error':
                            update_data.update(response_data)  # Include error info
                        
                        # Create and run the coroutine in the event loop
                        asyncio.create_task(
                            self.async_process_position_update(
                                position_id, 
                                update_data
                            )
                        )

                elif '/orders?' in flow.request.pretty_url and flow.request.method == "POST":
                    asyncio.create_task(
                        self.async_process_order(
                            dict(flow.request.urlencoded_form), 
                            response_data
                        )
                    )
                elif '/executions?' in flow.request.pretty_url:
                    asyncio.create_task(
                        self.async_process_execution(response_data)
                    )
                    
            except Exception as e:
                print(f"❌ Error processing response: {e}")

addons = [TradingViewInterceptor()]