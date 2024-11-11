import os
import json
import asyncio
from mitmproxy import ctx, http
from datetime import datetime
from dotenv import load_dotenv
from src.core.trade_handler import TradeHandler
from src.utils.token_manager import TokenManager

load_dotenv()
TV_BROKER_URL = os.getenv('TV_BROKER_URL')
TV_ACCOUNT_ID = os.getenv('TV_ACCOUNT_ID')

# Create a global token manager instance
GLOBAL_TOKEN_MANAGER = TokenManager()

class TradingViewInterceptor:
    def __init__(self):
        self.base_path = f"{TV_BROKER_URL}/accounts/{TV_ACCOUNT_ID}"
        self.trade_handler = TradeHandler()
        self.token_manager = GLOBAL_TOKEN_MANAGER  # Use global instance
        self.loop = asyncio.get_event_loop()
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

    async def async_process_order(self, request_data: dict, response_data: dict) -> None:
        """Asynchronously process order."""
        await self.trade_handler.process_order(request_data, response_data)

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
            print("\n📤 Trade Data:")
            print(json.dumps(dict(flow.request.urlencoded_form), indent=2))
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
                # Handle order and execution responses
                if '/orders?' in flow.request.pretty_url and flow.request.method == "POST":
                    # Create and run the coroutine in the event loop
                    asyncio.create_task(
                        self.async_process_order(
                            dict(flow.request.urlencoded_form), 
                            response_data
                        )
                    )
                elif '/executions?' in flow.request.pretty_url:
                    # Create and run the coroutine in the event loop
                    asyncio.create_task(
                        self.async_process_execution(response_data)
                    )
                    
            except Exception as e:
                print(f"❌ Error processing response: {e}")

addons = [TradingViewInterceptor()]