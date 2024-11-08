import MetaTrader5 as mt5
import logging
import json
from typing import Dict, Optional
from pathlib import Path
from src.services.mt5_service import MT5Service
from src.config.mt5_config import MT5_CONFIG

logger = logging.getLogger('SymbolMapper')

class SymbolMapper:
    """Maps TradingView symbols to MT5 symbols."""
    
    def __init__(self):
        # Core symbols that are always mapped
        self.mappings = {
            'BTCUSD': 'BTCUSD.r',
            'ETHUSD': 'ETHUSD.r',
            'XAUUSD': 'XAUUSD.r'
        }
        
        # Set up file path for mappings
        self.mappings_file = Path('data/symbol_mappings.json')
        self.mappings_file.parent.mkdir(exist_ok=True)
        
        # Get MT5 service instance
        self.mt5_service = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
        
        # Load or initialize mappings
        self._load_or_initialize_mappings()
    
    def _load_or_initialize_mappings(self) -> None:
        """Load existing mappings or initialize from MT5."""
        try:
            if self.mappings_file.exists():
                # Load from file
                with open(self.mappings_file, 'r') as f:
                    stored_mappings = json.load(f)
                    self.mappings.update(stored_mappings)
                    print(f"Loaded {len(stored_mappings)} symbol mappings")
            else:
                # Initialize from MT5
                self._initialize_mt5_mappings()
                
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            self._initialize_mt5_mappings()
    
    def _initialize_mt5_mappings(self) -> None:
        """Initialize symbol mappings from MT5."""
        try:
            if not self.mt5_service.initialize():
                logger.error("Failed to initialize MT5")
                return
            
            # Get all symbols
            symbols = mt5.symbols_get()
            if symbols is None:
                logger.error("Failed to get MT5 symbols")
                return
            
            # Process each symbol
            for sym in symbols:
                base_symbol = sym.name.replace('.a', '')
                if base_symbol not in self.mappings:
                    self.mappings[base_symbol] = sym.name
            
            # Save to file
            self._save_mappings()
            print(f"Updated mappings with {len(self.mappings)} symbols")
            
        except Exception as e:
            logger.error(f"Error initializing mappings: {e}")
    
    def _save_mappings(self) -> None:
        """Save mappings to file."""
        try:
            with open(self.mappings_file, 'w') as f:
                json.dump(self.mappings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")
    
    def get_mt5_symbol(self, tv_symbol: str) -> str:
        """Convert TradingView symbol to MT5 symbol."""
        return self.mappings.get(tv_symbol, f"{tv_symbol}.a")
    
    def get_tv_symbol(self, mt5_symbol: str) -> str:
        """Convert MT5 symbol to TradingView symbol."""
        return mt5_symbol.replace('.a', '')
    
    def refresh_mappings(self) -> None:
        """Refresh mappings from MT5."""
        self._initialize_mt5_mappings()
    
    def add_mapping(self, tv_symbol: str, mt5_symbol: str) -> None:
        """Manually add a symbol mapping."""
        self.mappings[tv_symbol] = mt5_symbol
        self._save_mappings()
        print(f"Added mapping: {tv_symbol} → {mt5_symbol}")

    def remove_mapping(self, tv_symbol: str) -> None:
        """Remove a symbol mapping."""
        if tv_symbol in self.mappings:
            del self.mappings[tv_symbol]
            self._save_mappings()
            print(f"Removed mapping for {tv_symbol}")