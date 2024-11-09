import logging
import json
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger('TokenManager')

class TokenManager:
    def __init__(self):
        self._token = None
        self._token_file = Path('data/auth_token.json')
        self._token_file.parent.mkdir(exist_ok=True)
        self._load_token()
    
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
                    self._token_file.unlink(missing_ok=True)
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
            logger.info("Token saved to file")
        except Exception as e:
            logger.error(f"Error saving token: {e}")
    
    def update_token(self, token: str) -> None:
        """Update the stored token."""
        if token.startswith('Bearer '):
            self._token = token
        else:
            self._token = f"Bearer {token}"
        self._save_token()
        logger.info("Authorization token updated")
    
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