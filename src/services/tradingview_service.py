import requests
import logging
from typing import Dict, Any, Optional
from src.utils.token_manager import TokenManager

logger = logging.getLogger('TradingViewService')

class TradingViewService:
    """Service to interact with TradingView API."""
    
    def __init__(self, account_id: str, token_manager: TokenManager):
        self.account_id = account_id
        self.token_manager = token_manager
        self.base_url = f"https://icmarkets.tv.ctrader.com/accounts/{account_id}"
    
    def close_position(self, position_id: str) -> Dict[str, Any]:
        """Close a position on TradingView."""
        try:            
            # Get and validate token
            token = self.token_manager.get_token()
            if not token:
                error_msg = "No authorization token available"
                logger.error(error_msg)
                print(f"❌ {error_msg}")
                print("Tip: Make sure to open TradingView interface first")
                return {"error": error_msg}
                        
            # Prepare request
            url = f"{self.base_url}/positions/{position_id}"
            params = {"locale": "en"}
            headers = self.token_manager.headers
            
            # Send request
            response = requests.delete(
                url,
                params=params,
                headers=headers,
                verify=False
            )
            
            if response.status_code == 200:
                logger.info(f"Position {position_id} closed successfully")
                return {"status": "success", "data": response.json()}
            else:
                error_msg = f"Failed to close position: {response.status_code} - {response.text}"
                logger.error(error_msg)
                print(f"❌ {error_msg}")
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"Error closing position: {e}"
            logger.error(error_msg)
            print(f"❌ {error_msg}")
            return {"error": error_msg}