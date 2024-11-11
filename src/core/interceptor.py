import os
import json
import asyncio
from mitmproxy import ctx, http
from datetime import datetime
from dotenv import load_dotenv
from src.core.trade_handler import TradeHandler
from src.utils.token_manager import TokenManager
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER

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
            print("\n🚀 Trade interceptor initialized")
            print("👀 Watching for trades...\n")
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
            # Match both DELETE and PUT methods
            return flow.request.method in ["DELETE", "PUT"]
                
        return False

    async def async_process_order(self, request_data: dict, response_data: dict) -> None:
        """Asynchronously process order."""
        await self.trade_handler.process_order(request_data, response_data)

    async def async_process_position_update(self, position_id: str, update_data: dict) -> None:
        """Asynchronously process position update."""
        await self.trade_handler.process_position_update(position_id, update_data)

    async def async_process_position_close(self, position_id: str) -> None:
        """Asynchronously process position close."""
        await self.trade_handler.process_position_close(position_id)

    async def async_process_execution(self, response_data: dict) -> None:
        """Asynchronously process execution."""
        await self.trade_handler.process_execution(response_data)

    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        # Capture auth token from all TradingView requests
        if self.base_path in flow.request.pretty_url:
            auth_header = flow.request.headers.get('authorization')
            if auth_header:
                self.token_manager.update_token(auth_header)
        
        if not self.should_log_request(flow):
            return
        
        if flow.request.method == "POST" and flow.request.urlencoded_form:
            request_data = dict(flow.request.urlencoded_form)
            
            # Get direction and instrument details
            side = request_data.get('side', '').lower()
            direction_emoji = "🔼" if side == 'buy' else "🔻"
            instrument = request_data.get('instrument', '')
            quantity = request_data.get('qty', '')

        elif flow.request.method == "DELETE":
            # Extract position ID from URL
            url_parts = flow.request.pretty_url.split('/')
            position_id = url_parts[-1].split('?')[0]
            # Create and run the coroutine in the event loop
            asyncio.create_task(self.async_process_position_close(position_id))

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
                        
                        # Get update data from request
                        update_data = dict(flow.request.urlencoded_form)
                        
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