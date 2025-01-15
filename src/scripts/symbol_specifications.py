import os
import pandas as pd
import MetaTrader5 as mt5
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger('SwapAnalyzer')

class SymbolSpecifications:
    def __init__(self):
        self.terminal_path = os.getenv('MT5_TERMINAL_PATH')
        self.account = int(os.getenv('MT5_ACCOUNT'))
        self.password = os.getenv('MT5_PASSWORD')
        self.server = os.getenv('MT5_SERVER')
        
    def initialize(self) -> bool:
        """Initialize MT5 connection."""
        try:
            # Initialize MT5
            if not mt5.initialize(
                login=self.account,
                password=self.password,
                server=self.server,
                path=self.terminal_path
            ):
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
                
            # Verify connection
            if not mt5.account_info():
                logger.error("Failed to connect to MT5 account")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error initializing MT5: {e}")
            return False
            
    def get_all_symbols(self) -> List[str]:
        """Get all available symbols from MT5."""
        try:
            symbols = mt5.symbols_get()
            return [symbol.name for symbol in symbols]
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []
            
    def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        """Get detailed specifications for a symbol."""
        try:
            # Select the symbol
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Failed to select symbol {symbol}")
                return {}
                
            # Get specifications
            specs = mt5.symbol_info(symbol)
            if not specs:
                logger.error(f"No specifications found for {symbol}")
                return {}
                
            # Extract relevant information
            return {
                'symbol': symbol,
                'description': specs.description,
                'base_currency': getattr(specs, 'currency_base', ''),
                'profit_currency': getattr(specs, 'currency_profit', ''),
                'type': self._get_symbol_type(specs.path),
                'trade_contract_size': specs.trade_contract_size,
                'volume_min': specs.volume_min,
                'volume_max': specs.volume_max,
                'volume_step': specs.volume_step,
                'swap_long': specs.swap_long,
                'swap_short': specs.swap_short,
                'swap_mode': self._get_swap_mode(specs.swap_mode),
                'swap_rollover3days': specs.swap_rollover3days,
                'margin_initial': specs.margin_initial,
                'margin_maintenance': specs.margin_maintenance,
                'pip_value': self._calculate_pip_value(specs),
                'points': specs.point,
                'digits': specs.digits,
                'spread': specs.spread,
                'tick_size': specs.trade_tick_size,
                'tick_value': specs.trade_tick_value,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"Error getting specifications for {symbol}: {e}")
            return {}
            
    def _get_symbol_type(self, path: str) -> str:
        """Determine symbol type from its path."""
        path = path.lower()
        if 'forex' in path:
            return 'Forex'
        elif 'crypto' in path:
            return 'Crypto'
        elif 'indices' in path or 'index' in path:
            return 'Index'
        elif 'commodities' in path:
            if any(metal in path for metal in ['gold', 'silver', 'platinum', 'palladium']):
                return 'Metals'
            return 'Commodities'
        return 'Other'
        
    def _get_swap_mode(self, mode: int) -> str:
        """Convert swap mode number to description."""
        modes = {
            0: "Points",
            1: "Currency symbol base rate",
            2: "Interest - buy",
            3: "Interest - sell",
            4: "Currency margin rate",
            5: "Currency profit rate",
            6: "Cross rate",
            7: "Interest rate for currency pairs"
        }
        return modes.get(mode, f"Unknown ({mode})")
        
    def _calculate_pip_value(self, specs) -> float:
        """Calculate pip value for the symbol."""
        try:
            # Get current price
            tick = mt5.symbol_info_tick(specs.name)
            if not tick:
                return 0.0
                
            price = (tick.bid + tick.ask) / 2
            
            # Calculate pip value
            point = specs.point
            trade_contract_size = specs.trade_contract_size
            
            if specs.digits == 3 or specs.digits == 5:
                point *= 10
                
            pip_value = point * trade_contract_size
            if specs.currency_profit != "USD":
                # Convert to USD if needed
                conversion_symbol = f"{specs.currency_profit}USD"
                conversion_tick = mt5.symbol_info_tick(conversion_symbol)
                if conversion_tick:
                    pip_value *= (conversion_tick.bid + conversion_tick.ask) / 2
                    
            return round(pip_value, 6)
            
        except Exception as e:
            logger.error(f"Error calculating pip value: {e}")
            return 0.0
            
    def analyze_swaps(self, output_file: str = "symbol_specifications.xlsx"):
        """Analyze swaps for all symbols and export to Excel."""
        try:
            if not self.initialize():
                return
                
            print("\nAnalyzing swap rates...")
            print("This may take a few minutes...")
            
            # Get all symbols
            symbols = self.get_all_symbols()
            total = len(symbols)
            
            # Collect data
            data = []
            for i, symbol in enumerate(symbols, 1):
                print(f"Processing {symbol} ({i}/{total})", end='\r')
                specs = self.get_symbol_specs(symbol)
                if specs:
                    data.append(specs)
                    
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Organize columns
            columns = [
                'symbol', 'description', 'type', 'base_currency', 'profit_currency',
                'swap_long', 'swap_short', 'swap_mode', 'swap_rollover3days',
                'trade_contract_size', 'pip_value', 'points', 'digits',
                'spread', 'tick_size', 'tick_value',
                'volume_min', 'volume_max', 'volume_step',
                'margin_initial', 'margin_maintenance',
                'updated_at'
            ]
            
            df = df[columns]
            
            # Calculate daily swap cost in USD for 1 lot
            df['swap_long_usd'] = df.apply(lambda x: x['swap_long'] * x['pip_value'], axis=1)
            df['swap_short_usd'] = df.apply(lambda x: x['swap_short'] * x['pip_value'], axis=1)
            
            # Sort by type and symbol
            df = df.sort_values(['type', 'symbol'])
            
            # Export to Excel with formatting
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Write all symbols
                df.to_excel(writer, sheet_name='All Symbols', index=False)
                
                # Create sheets by type
                for symbol_type in df['type'].unique():
                    type_df = df[df['type'] == symbol_type]
                    type_df.to_excel(writer, sheet_name=symbol_type, index=False)
                    
            print(f"\n\nAnalysis complete! File saved as: {output_file}")
            print(f"Total symbols analyzed: {len(df)}")
            print("\nSymbols by type:")
            print(df['type'].value_counts().to_string())
            
        except Exception as e:
            logger.error(f"Error in swap analysis: {e}")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    analyzer = SymbolSpecifications()
    analyzer.analyze_swaps()