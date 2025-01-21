import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

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
            self._last_refresh = None
            self._token_expiry = timedelta(minutes=30)  # More conservative expiry
            # Store token file in user's home directory
            self._token_file = Path.home() / '.tradingview' / 'token.json'
            self._load_token()
            self._initialized = True
    

    def _load_token(self) -> None:
        """Load token with better error handling and expiry check."""
        try:
            # First check if current in-memory token is still valid
            if self._token and self._last_refresh:
                if datetime.now() - self._last_refresh < self._token_expiry:
                    logger.debug("Using valid in-memory token")
                    return

            # Function to validate token data
            def is_valid_token_data(data: dict) -> bool:
                if not isinstance(data, dict):
                    return False
                if not all(key in data for key in ['token', 'timestamp']):
                    return False
                try:
                    token_time = datetime.fromisoformat(data['timestamp'])
                    return datetime.now() - token_time < self._token_expiry
                except (ValueError, TypeError):
                    return False

            # Function to load token from file
            def load_from_file(file_path: Path) -> bool:
                if not file_path.exists() or file_path.stat().st_size == 0:
                    return False
                
                try:
                    data = json.loads(file_path.read_text())
                    if is_valid_token_data(data):
                        self._token = data['token']
                        self._last_refresh = datetime.fromisoformat(data['timestamp'])
                        self._token_file = file_path  # Update token file path
                        logger.debug(f"Token loaded from {file_path}")
                        return True
                except json.JSONDecodeError:
                    logger.warning(f"Token file corrupted: {file_path}")
                except Exception as e:
                    logger.warning(f"Error reading token from {file_path}: {e}")
                return False

            # Try primary location first
            if load_from_file(self._token_file):
                return

            # Try alternate location
            alt_path = Path(os.getcwd()) / '.tv_token.json'
            if load_from_file(alt_path):
                return

            # No valid token found
            logger.info("No valid token found in any location")
            self._token = None
            self._last_refresh = None

        except Exception as e:
            logger.error(f"Error loading token: {e}")
            self._token = None
            self._last_refresh = None

    def _save_token(self) -> None:
        """Save token with better error handling."""
        try:
            if not self._token:
                logger.warning("Attempted to save empty token")
                return

            data = {
                'token': self._token,
                'timestamp': datetime.now().isoformat()
            }
            
            # Try primary location first
            try:
                self._token_file.parent.mkdir(parents=True, exist_ok=True)
                self._token_file.write_text(json.dumps(data, indent=2))
                logger.debug("Token saved successfully")
                return
            except PermissionError:
                logger.warning("Permission denied at primary location")
            
            # Try alternate location
            try:
                alt_path = Path(os.getcwd()) / '.tv_token.json'
                alt_path.write_text(json.dumps(data, indent=2))
                self._token_file = alt_path  # Update token file path
                logger.debug(f"Token saved to alternate location: {alt_path}")
            except Exception as e:
                logger.error(f"Could not save token to alternate location: {e}")
                
        except Exception as e:
            logger.error(f"Error saving token: {e}")
    
    def update_token(self, token: str) -> None:
        """Update the stored token only if it's different from current token."""
        if not token:
            logger.warning("Attempted to update with empty token")
            return
            
        # Remove duplicate 'Bearer' if present
        token = token.replace('Bearer Bearer', 'Bearer')
        if not token.startswith('Bearer '):
            token = f"Bearer {token}"
        
        # Only update if token has changed
        if token != self._token:
            self._token = token
            self._last_refresh = datetime.now()
            self._save_token()
            logger.info("Token updated successfully")
        else:
            logger.debug("Token unchanged, skipping update")
        
    def is_token_valid(self) -> Tuple[bool, str]:
        """Check if current token is valid and not expired."""
        if not self._token:
            return False, "No token available"
            
        if not self._last_refresh:
            return False, "Token refresh time unknown"
            
        if datetime.now() - self._last_refresh > self._token_expiry:
            return False, "Token has expired"
            
        return True, "Token is valid"
        
    def get_token(self) -> Optional[str]:
        """Get the current token with validation."""
        if not self._token:
            self._load_token()
            
        is_valid, reason = self.is_token_valid()
        if not is_valid:
            logger.warning(f"Invalid token: {reason}")
            return None
            
        return self._token

# Add this method to your src/utils/token_manager.py file

    def get_token_info(self) -> dict:
        """Get information about the current token and its file."""
        token_file = self._token_file
        if not token_file.exists():
            token_file = Path(os.getcwd()) / '.tv_token.json'
        
        try:
            mod_time = token_file.stat().st_mtime if token_file.exists() else None
            last_modified = datetime.fromtimestamp(mod_time) if mod_time else None
        except Exception as e:
            last_modified = None
            logger.error(f"Error getting file modification time: {e}")
        
        return {
            'token_exists': bool(self._token),
            'last_refresh': self._last_refresh,
            'file_path': str(token_file),
            'file_exists': token_file.exists(),
            'last_modified': last_modified,
            'file_size': token_file.stat().st_size if token_file.exists() else 0,
            'is_valid': self.is_token_valid()[0] if hasattr(self, 'is_token_valid') else None
        }

    def refresh_token(self) -> Optional[str]:
        """Attempt to refresh the token from TradingView."""
        # logger.info("Token refresh requested")
        # Force reload from disk in case another process updated it
        self._load_token()
        
        is_valid, reason = self.is_token_valid()
        if is_valid:
            # logger.info("Token is still valid, no refresh needed")
            return self._token
            
        # If we got here, we need a new token
        logger.warning(f"Token needs refresh: {reason}")
        self._token = None
        self._last_refresh = None
        return None
        
    @property
    def headers(self) -> dict:
        """Get headers with authorization and additional debugging info."""
        token = self.get_token()
        if not token:
            logger.warning("No valid token available for headers")
            return {}
            
        headers = {
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
        
        # Log headers for debugging (excluding sensitive info)
        debug_headers = headers.copy()
        debug_headers['authorization'] = 'Bearer ***'
        logger.debug(f"Generated headers: {debug_headers}")
        
        return headers

# Create global instance
GLOBAL_TOKEN_MANAGER = TokenManager()