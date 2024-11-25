import asyncio
import logging
import os
from typing import Any, Dict

import aiohttp
from dotenv import load_dotenv

from src.utils.token_manager import TokenManager

logger = logging.getLogger('TradingViewService')

load_dotenv()
TV_BROKER_URL = os.getenv('TV_BROKER_URL')
TV_ACCOUNT_ID = os.getenv('TV_ACCOUNT_ID')

class TradingViewService:
    """Service to interact with TradingView API."""
    
    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self.base_url = f"https://{TV_BROKER_URL}/accounts/{TV_ACCOUNT_ID}"
        self.session = None
        self.loop = asyncio.get_event_loop()
        # Use local proxy for routing through mitmproxy
        self.proxies = {
            'http': 'http://localhost:8080',
            'https': 'http://localhost:8080'
        }
    
    async def async_close_position(self, position_id: str) -> Dict[str, Any]:
        """Close a position on TradingView asynchronously."""
        try:            
            # Get and validate token
            token = self.token_manager.get_token()
            if not token:
                error_msg = "No authorization token available"
                logger.error(error_msg)
                print(f"❌ {error_msg}")
                print("Tip: Make sure to open TradingView interface first")
                return {"error": error_msg}
                        
            # Validate position_id
            if not position_id:
                error_msg = "Invalid position ID"
                logger.error(error_msg)
                return {"error": error_msg}

            # Prepare request
            url = f"{self.base_url}/positions/{position_id}"
            params = {"locale": "en"}
            headers = self.token_manager.headers

            # Create session if needed
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Send request through proxy
            async with self.session.delete(
                url,
                params=params,
                headers=headers,
                ssl=False,
                proxy=self.proxies['http']
            ) as response:
                status_code = response.status
                if status_code == 200:
                    data = await response.json()
                    return {"status": "success", "data": data}
                elif status_code == 404:
                    # Position might already be closed
                    logger.info(f"Position {position_id} not found (might already be closed)")
                    return {
                        "status": "success", 
                        "data": {
                            "message": "Position not found or already closed",
                            "position_id": position_id,
                            "status_code": 404
                        }
                    }
                else:
                    response_text = await response.text()
                    error_msg = f"Failed to close position: Status {status_code}, Response: {response_text}"
                    logger.error(error_msg)
                    print(f"❌ {error_msg}")
                    return {"error": error_msg, "status_code": status_code}
                
        except Exception as e:
            error_msg = f"Error closing position: {e}"
            logger.error(error_msg)
            print(f"❌ {error_msg}")
            return {"error": error_msg}

    def close_position(self, position_id: str) -> Dict[str, Any]:
        """Synchronous version of close_position for compatibility."""
        return asyncio.run(self.async_close_position(position_id))
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None