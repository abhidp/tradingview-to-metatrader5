# config/mt5_symbol_config.py

import os
import json
from typing import Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get default suffix from environment or use fallback
DEFAULT_SUFFIX = os.getenv('MT5_DEFAULT_SUFFIX', '.a')

# Load symbol map from environment or use empty dict
try:
    SYMBOL_MAP = json.loads(os.getenv('MT5_SYMBOL_MAP', '{}'))
except json.JSONDecodeError:
    SYMBOL_MAP = {}

class SymbolMapper:
    def __init__(self, suffix: str = DEFAULT_SUFFIX, custom_map: Dict[str, str] = None):
        self.suffix = suffix
        self.custom_map = custom_map or SYMBOL_MAP
        
    def map_symbol(self, tv_symbol: str) -> str:
        """Map TradingView symbol to MT5 symbol."""
        # Check custom mapping first
        if tv_symbol in self.custom_map:
            return self.custom_map[tv_symbol]
        
        # Apply default suffix if no custom mapping
        return f"{tv_symbol}{self.suffix}"
    
    def add_mapping(self, tv_symbol: str, mt5_symbol: str) -> None:
        """Add a custom symbol mapping."""
        self.custom_map[tv_symbol] = mt5_symbol
    
    def remove_mapping(self, tv_symbol: str) -> None:
        """Remove a custom symbol mapping."""
        self.custom_map.pop(tv_symbol, None)
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Get all custom symbol mappings."""
        return self.custom_map.copy()