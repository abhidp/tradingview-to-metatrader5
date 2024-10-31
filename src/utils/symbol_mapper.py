from typing import Dict, Optional

class SymbolMapper:
    """Maps TradingView symbols to MT5 symbols."""
    
    # Default symbol mappings
    DEFAULT_MAPPINGS = {
        'BTCUSD': 'BTCUSD.a',
        'ETHUSD': 'ETHUSD.a',
        'XAUUSD': 'XAUUSD.a',
        # Add more mappings as needed
    }
    
    def __init__(self, custom_mappings: Dict[str, str] = None):
        """Initialize with optional custom mappings."""
        self.mappings = self.DEFAULT_MAPPINGS.copy()
        if custom_mappings:
            self.mappings.update(custom_mappings)
    
    def get_mt5_symbol(self, tv_symbol: str) -> str:
        """Convert TradingView symbol to MT5 symbol."""
        return self.mappings.get(tv_symbol, f"{tv_symbol}.a")
    
    def get_tv_symbol(self, mt5_symbol: str) -> Optional[str]:
        """Convert MT5 symbol to TradingView symbol."""
        # Remove .a suffix if present
        base_symbol = mt5_symbol.replace('.a', '')
        return base_symbol