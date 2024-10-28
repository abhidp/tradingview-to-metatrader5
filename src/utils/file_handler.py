import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from src.config.settings import TRADES_DIR, TRADE_FILE_PREFIX

class TradeFileHandler:
    """Handles trade file operations."""
    
    def __init__(self):
        self.session_file = TRADES_DIR / f"{TRADE_FILE_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.is_first_trade = True
        self._initialize_file()
    
    def _initialize_file(self):
        """Initialize the JSON file with an empty array."""
        with open(self.session_file, 'w', encoding='utf-8') as f:
            f.write('[\n')
    
    def write_trade(self, trade_data: Dict[str, Any]):
        """Write trade data to file with proper JSON formatting."""
        try:
            json_str = json.dumps(trade_data, indent=2)
            
            with open(self.session_file, 'a', encoding='utf-8') as f:
                if not self.is_first_trade:
                    f.write(',\n')
                f.write(json_str)
                self.is_first_trade = False
                
        except Exception as e:
            logging.error(f"Error writing trade: {e}")
    
    def close_file(self):
        """Close the JSON array in the file."""
        try:
            with open(self.session_file, 'a', encoding='utf-8') as f:
                f.write('\n]')
        except Exception as e:
            logging.error(f"Error closing trade file: {e}")

    def get_filepath(self) -> Path:
        """Return the current session file path."""
        return self.session_file