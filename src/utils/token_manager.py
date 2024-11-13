# utils/token_manager.py

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger('TokenManager')

class TokenManager:
    """Manages TradingView authorization token."""
    
    _instance = None  # Singleton instance
    _initialized = False  # Initialization flag
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TokenManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:  # Only initialize once
            self._token = None
            self._token_file = Path('token.json')
            self._load_token()
            self._initialized = True
    
    def _load_token(self) -> None:
        """Load token from file."""
        try:
            if self._token_file.exists():
                data = json.loads(self._token_file.read_text())
                if datetime.fromisoformat(data['timestamp']) > datetime.now() - timedelta(hours=1):
                    self._token = data['token']
                    logger.info("Token loaded from file")
                else:
                    logger.info("Stored token expired")
        except Exception as e:
            logger.error(f"Error loading token: {e}")
    
    def _save_token(self) -> None:
        """Save token to file."""
        try:
            data = {
                'token': self._token,
                'timestamp': datetime.now().isoformat()
            }
            self._token_file.write_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Error saving token: {e}")
    
    def update_token(self, token: str) -> None:
        """Update the stored token."""
        if token.startswith('Bearer '):
            self._token = token
        else:
            self._token = f"Bearer {token}"
        self._save_token()
        
    def get_token(self) -> Optional[str]:
        """Get the current token."""
        if not self._token:
            self._load_token()
        return self._token
        
    @property
    def headers(self) -> dict:
        """Get headers with authorization."""
        token = self.get_token()
        if not token:
            return {}
            
        return {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': token,
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.tradingview.com',
            'pragma': 'no-cache',
            'referer': 'https://www.tradingview.com/',
            'sec-ch-ua': '"Chromium";v="130", "Brave";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site'
        }

# Create global instance
GLOBAL_TOKEN_MANAGER = TokenManager()