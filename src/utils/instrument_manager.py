import json
import logging
import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

logger = logging.getLogger('InstrumentManager')

class InstrumentManager:
    def __init__(self):
        load_dotenv()
        self.config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'
        self.default_suffix = os.getenv('MT5_DEFAULT_SUFFIX', '')
        self.instruments = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load instrument configuration."""
        try:
            # print(f"\n🔍 Looking for config file: {self.config_path}")
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # uncomment for testing
                    ''' 
                    print("✅ Found instruments.json")
                    print("\n📄 Current configuration:")
                    print(f"Total instruments: {len(config.get('instruments', {}).get('pairs', []))}")
                    print(f"Custom instruments: {len(config.get('custom', {}).get('pairs', []))}")
                    
                    # Print first few instruments as example
                    print("\nSample instruments:")
                    for pair in config.get('instruments', {}).get('pairs', []):
                        print(f"  - {pair['name']}: pip size {pair['pip_size']}")
                    print("  ...")
                    '''
                    return config
            else:
                # print("❌ instruments.json not found")
                return {}
                
        except Exception as e:
            logger.error(f"Error loading instrument config: {e}")
            # print("❌ Error reading configuration file")
            return {}  # Return empty dict if file not found

    def get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol."""
        try:
            # Remove suffix from symbol
            clean_symbol = symbol.replace(self.default_suffix, '')
            
            # Check regular instruments
            for pair in self.instruments.get('instruments', {}).get('pairs', []):
                if pair['name'] == clean_symbol:
                    return float(pair['pip_size'])
            
            # Check custom instruments
            for pair in self.instruments.get('custom', {}).get('pairs', []):
                if pair['name'] == clean_symbol:
                    return float(pair['pip_size'])
            
            logger.warning(f"No pip size found for {symbol}, using default 0.0001")
            return 0.0001
            
        except Exception as e:
            logger.error(f"Error getting pip size: {e}")
            return 0.0001

    def calculate_trailing_distance(self, symbol: str, trailing_pips: float, symbol_info) -> float:
        """Calculate trailing distance for a symbol."""
        try:
            pip_size = self.get_pip_size(symbol)
            
            # Calculate trailing distance
            trailing_distance = trailing_pips * float(pip_size)
            
            # Round to symbol digits
            trailing_distance = round(trailing_distance, symbol_info.digits)
            
            logger.debug(f"Trailing calculation for {symbol}:")
            logger.debug(f"Pip size: {pip_size}")
            logger.debug(f"Trailing pips: {trailing_pips}")
            logger.debug(f"Trailing distance: {trailing_distance}")
            
            return trailing_distance
            
        except Exception as e:
            logger.error(f"Error calculating trailing distance: {e}")
            return 0.0