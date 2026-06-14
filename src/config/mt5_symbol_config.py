"""TradingView->MT5 symbol mapping, sourced from the settings store (was .env)."""
from typing import Dict

from app.config_accessors import get_symbol_settings


class SymbolMapper:
    def __init__(self, suffix: str = None, custom_map: Dict[str, str] = None):
        default_suffix, default_map = get_symbol_settings()
        self.suffix = suffix if suffix is not None else default_suffix
        self.custom_map = custom_map if custom_map is not None else default_map

    def map_symbol(self, tv_symbol: str) -> str:
        """Map TradingView symbol to MT5 symbol."""
        if tv_symbol in self.custom_map:
            return self.custom_map[tv_symbol]
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
