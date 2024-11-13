import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Set

import MetaTrader5 as mt5

from src.config.mt5_config import MT5_CONFIG
from src.services.mt5_service import MT5Service

logger = logging.getLogger('SymbolMapper')

class SymbolMapper:
    """Maps TradingView symbols to MT5 symbols with caching."""
    
    def __init__(self, default_suffix='.r'):
        self.default_suffix = default_suffix
        
        # Core symbols that are always mapped
        self.mappings = {
            'BTCUSD': f'BTCUSD{self.default_suffix}',
            'ETHUSD': f'ETHUSD{self.default_suffix}',
            'XAUUSD': f'XAUUSD{self.default_suffix}'
        }
        
        # Cache for MT5 symbols
        self._symbol_cache = {}
        self._cache_timestamp = None
        self._cache_duration = timedelta(hours=4)  # Cache refresh interval
        
        # Track active symbols for prioritized caching
        self._active_symbols: Set[str] = set()
        
        # Set up file path for mappings
        self.mappings_file = Path('data/symbol_mappings.json')
        self.mappings_file.parent.mkdir(exist_ok=True)
        
        # Get MT5 service instance
        self.mt5_service = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
        
        # Load or initialize mappings and cache
        self._load_or_initialize_mappings()
        self._initialize_symbol_cache()
    
    def _should_refresh_cache(self) -> bool:
        """Check if the cache needs refreshing."""
        if self._cache_timestamp is None:
            return True
        return datetime.now() - self._cache_timestamp > self._cache_duration
    
    def _initialize_symbol_cache(self) -> None:
        """Initialize the symbol cache with all available symbols."""
        try:
            if not self.mt5_service.initialize():
                logger.error("Failed to initialize MT5 for cache")
                return
            
            symbols = mt5.symbols_get()
            if symbols is None:
                logger.error("Failed to get MT5 symbols for cache")
                return
            
            # Update cache with symbol objects
            for symbol in symbols:
                self._symbol_cache[symbol.name] = {
                    'digits': symbol.digits,
                    'point': symbol.point,
                    'trade_contract_size': symbol.trade_contract_size,
                    'volume_min': symbol.volume_min,
                    'volume_max': symbol.volume_max,
                    'volume_step': symbol.volume_step
                }
            
            self._cache_timestamp = datetime.now()
            logger.info(f"Initialized symbol cache with {len(self._symbol_cache)} symbols")
            
        except Exception as e:
            logger.error(f"Error initializing symbol cache: {e}")
    
    def _refresh_cache_if_needed(self) -> None:
        """Refresh the cache if it's expired."""
        if self._should_refresh_cache():
            logger.info("Refreshing symbol cache")
            self._initialize_symbol_cache()
    
    def get_symbol_info(self, mt5_symbol: str) -> Optional[Dict]:
        """Get cached symbol information, refreshing if necessary."""
        self._refresh_cache_if_needed()
        
        # Add to active symbols set for prioritized caching
        self._active_symbols.add(mt5_symbol)
        
        # Return cached info if available
        if mt5_symbol in self._symbol_cache:
            return self._symbol_cache[mt5_symbol]
        
        # If not in cache, try to fetch individually
        try:
            symbol_info = mt5.symbol_info(mt5_symbol)
            if symbol_info is not None:
                self._symbol_cache[mt5_symbol] = {
                    'digits': symbol_info.digits,
                    'point': symbol_info.point,
                    'trade_contract_size': symbol_info.trade_contract_size,
                    'volume_min': symbol_info.volume_min,
                    'volume_max': symbol_info.volume_max,
                    'volume_step': symbol_info.volume_step
                }
                return self._symbol_cache[mt5_symbol]
        except Exception as e:
            logger.error(f"Error fetching symbol info for {mt5_symbol}: {e}")
        
        return None
    
    def _load_or_initialize_mappings(self) -> None:
        """Load existing mappings or initialize from MT5."""
        try:
            if self.mappings_file.exists():
                with open(self.mappings_file, 'r') as f:
                    stored_mappings = json.load(f)
                    self.mappings.update(stored_mappings)
                    logger.info(f"Loaded {len(stored_mappings)} symbol mappings")
            else:
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
            
            symbols = mt5.symbols_get()
            if symbols is None:
                logger.error("Failed to get MT5 symbols")
                return
            
            for sym in symbols:
                base_symbol = sym.name.replace(self.default_suffix, '')
                if base_symbol not in self.mappings:
                    self.mappings[base_symbol] = sym.name
            
            self._save_mappings()
            logger.info(f"Updated mappings with {len(self.mappings)} symbols")
            
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
        return self.mappings.get(tv_symbol, f"{tv_symbol}{self.default_suffix}")
    
    def get_tv_symbol(self, mt5_symbol: str) -> str:
        """Convert MT5 symbol to TradingView symbol."""
        return mt5_symbol.replace(self.default_suffix, '')
    
    def refresh_mappings(self) -> None:
        """Refresh both mappings and symbol cache from MT5."""
        self._initialize_mt5_mappings()
        self._initialize_symbol_cache()
    
    def add_mapping(self, tv_symbol: str, mt5_symbol: str) -> None:
        """Manually add a symbol mapping."""
        self.mappings[tv_symbol] = mt5_symbol
        self._save_mappings()
        logger.info(f"Added mapping: {tv_symbol} → {mt5_symbol}")

    def remove_mapping(self, tv_symbol: str) -> None:
        """Remove a symbol mapping."""
        if tv_symbol in self.mappings:
            del self.mappings[tv_symbol]
            self._save_mappings()
            logger.info(f"Removed mapping for {tv_symbol}")