import json
import logging
import os
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
            # Store token file in user's home directory
            self._token_file = Path.home() / '.tradingview' / 'token.json'
            self._load_token()
            self._initialized = True
    
    def _load_token(self) -> None:
        """Load token with better error handling."""
        try:
            # Try primary location
            if self._token_file.exists() and self._token_file.stat().st_size > 0:
                try:
                    data = json.loads(self._token_file.read_text())
                    if isinstance(data, dict) and 'token' in data and 'timestamp' in data:
                        if datetime.fromisoformat(data['timestamp']) > datetime.now() - timedelta(hours=1):
                            self._token = data['token']
                            logger.info("✅ Token loaded successfully")
                            return
                except json.JSONDecodeError:
                    logger.warning("⚠️  Token file corrupted")
                    
            # Try alternate location
            alt_path = Path(os.getcwd()) / '.tv_token.json'
            if alt_path.exists() and alt_path.stat().st_size > 0:
                try:
                    data = json.loads(alt_path.read_text())
                    if datetime.fromisoformat(data['timestamp']) > datetime.now() - timedelta(hours=1):
                        self._token = data['token']
                        self._token_file = alt_path  # Update token file path
                        logger.info("✅ Token loaded from alternate location")
                        return
                except:
                    pass
                    
            logger.info("⚠️  No valid token found")
            self._token = None
            
        except Exception as e:
            logger.error(f"❌ Error loading token: {e}")
            self._token = None
    
    def _save_token(self) -> None:
        """Save token with better error handling."""
        try:
            if not self._token:
                logger.warning("⚠️  Attempted to save empty token")
                return

            data = {
                'token': self._token,
                'timestamp': datetime.now().isoformat()
            }
            
            # Try primary location first
            try:
                self._token_file.parent.mkdir(parents=True, exist_ok=True)
                self._token_file.write_text(json.dumps(data, indent=2))
                logger.info("✅ Token saved successfully")
                return
            except PermissionError:
                logger.warning("⚠️  Permission denied at primary location")
            
            # Try alternate location
            try:
                alt_path = Path(os.getcwd()) / '.tv_token.json'
                alt_path.write_text(json.dumps(data, indent=2))
                self._token_file = alt_path  # Update token file path
                logger.info(f"✅ Token saved to alternate location: {alt_path}")
            except Exception as e:
                logger.error(f"❌ Could not save token to alternate location: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error saving token: {e}")
    
    def update_token(self, token: str) -> None:
        """Update the stored token."""
        if not token:
            logger.warning("⚠️  Attempted to update with empty token")
            return
            
        # Remove duplicate 'Bearer' if present
        token = token.replace('Bearer Bearer', 'Bearer')
        if token.startswith('Bearer '):
            self._token = token
        else:
            self._token = f"Bearer {token}"
            
        self._save_token()
        logger.info("✅ Token updated successfully")
        
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
            logger.warning("⚠️  No valid token available")
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
