'''
Usage:
=============
Update                : `python src/scripts/manage_symbols.py --suffix .r`
Add custom mapping    : `python src/scripts/manage_symbols.py --add BTCUSD BTCUSD.r`
Remove mapping        : `python src/scripts/manage_symbols.py --remove BTCUSD`
List all mappings     : `python src/scripts/manage_symbols.py --list`
List all MT5 symbols  : `python src/scripts/manage_symbols.py --mt5-symbols`
Filter symbols        : `python src/scripts/manage_symbols.py --mt5-symbols --filter USD`
See specific pairs    : `python src/scripts/manage_symbols.py --mt5-symbols --filter BTC`
'''

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import MetaTrader5 as mt5
from tabulate import tabulate

# Add project root to Python path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.config.mt5_config import MT5_CONFIG
from src.config.mt5_symbol_config import SymbolMapper


def initialize_mt5() -> bool:
    """Initialize MT5 connection."""
    if not mt5.initialize(
        login=MT5_CONFIG['account'],
        password=MT5_CONFIG['password'],
        server=MT5_CONFIG['server']
    ):
        print(f"❌ Failed to initialize MT5: {mt5.last_error()}")
        return False
    return True

def get_mt5_symbols() -> List[Dict]:
    """Get all available symbols from MT5."""
    try:
        # Get all symbols
        symbols = mt5.symbols_get()
        if symbols is None:
            print(f"❌ Failed to get symbols: {mt5.last_error()}")
            return []

        # Convert to list of dicts with relevant info
        symbol_info = []
        for sym in symbols:
            info = {
                'name': sym.name,
                'description': sym.description,
                'path': sym.path,
                'point': sym.point,
                'trade_contract_size': sym.trade_contract_size,
                'digits': sym.digits,
                'trade_mode': get_trade_mode(sym.trade_mode)
            }
            symbol_info.append(info)
        
        return symbol_info
    except Exception as e:
        print(f"❌ Error getting symbols: {e}")
        return []

def get_trade_mode(mode: int) -> str:
    """Convert trade mode number to string."""
    modes = {
        mt5.SYMBOL_TRADE_MODE_DISABLED: "Disabled",
        mt5.SYMBOL_TRADE_MODE_LONGONLY: "Long Only",
        mt5.SYMBOL_TRADE_MODE_SHORTONLY: "Short Only",
        mt5.SYMBOL_TRADE_MODE_CLOSEONLY: "Close Only",
        mt5.SYMBOL_TRADE_MODE_FULL: "Full Access"
    }
    return modes.get(mode, "Unknown")

def save_mappings_to_env(mappings: Dict[str, str]) -> None:
    """Save mappings to .env file."""
    env_path = project_root / '.env'
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    new_mapping = f'MT5_SYMBOL_MAP={json.dumps(mappings)}\n'
    mapping_found = False
    
    for i, line in enumerate(lines):
        if line.startswith('MT5_SYMBOL_MAP='):
            lines[i] = new_mapping
            mapping_found = True
            break
    
    if not mapping_found:
        lines.append(new_mapping)
    
    with open(env_path, 'w') as f:
        f.writelines(lines)

def main():
    parser = argparse.ArgumentParser(description='Manage MT5 symbol mappings')
    parser.add_argument('--add', nargs=2, metavar=('TV_SYMBOL', 'MT5_SYMBOL'),
                       help='Add a new symbol mapping')
    parser.add_argument('--remove', metavar='TV_SYMBOL',
                       help='Remove a symbol mapping')
    parser.add_argument('--list', action='store_true',
                       help='List all symbol mappings')
    parser.add_argument('--suffix', help='Update default suffix')
    parser.add_argument('--mt5-symbols', action='store_true',
                       help='List all available MT5 symbols')
    parser.add_argument('--filter', help='Filter MT5 symbols (e.g., "USD" or "BTC")')
    
    args = parser.parse_args()
    
    # Initialize MT5 if needed
    if args.mt5_symbols:
        if not initialize_mt5():
            return
    
    symbol_mapper = SymbolMapper()
    
    if args.add:
        tv_symbol, mt5_symbol = args.add
        symbol_mapper.add_mapping(tv_symbol, mt5_symbol)
        save_mappings_to_env(symbol_mapper.get_all_mappings())
        print(f"✅ Added mapping: {tv_symbol} -> {mt5_symbol}")
    
    elif args.remove:
        symbol_mapper.remove_mapping(args.remove)
        save_mappings_to_env(symbol_mapper.get_all_mappings())
        print(f"✅ Removed mapping for {args.remove}")
    
    elif args.suffix:
        env_path = project_root / '.env'
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        suffix_found = False
        for i, line in enumerate(lines):
            if line.startswith('MT5_DEFAULT_SUFFIX='):
                lines[i] = f'MT5_DEFAULT_SUFFIX={args.suffix}\n'
                suffix_found = True
                break
        
        if not suffix_found:
            lines.append(f'MT5_DEFAULT_SUFFIX={args.suffix}\n')
        
        with open(env_path, 'w') as f:
            f.writelines(lines)
        print(f"✅ Updated default suffix to {args.suffix}")
    
    elif args.mt5_symbols:
        symbols = get_mt5_symbols()
        
        # Apply filter if provided
        if args.filter:
            filter_text = args.filter.upper()
            symbols = [s for s in symbols if filter_text in s['name'].upper()]
        
        if symbols:
            # Prepare data for tabulate
            headers = ['Symbol', 'Description', 'Contract Size', 'Digits', 'Trade Mode']
            rows = [[
                s['name'],
                s['description'],
                s['trade_contract_size'],
                s['digits'],
                s['trade_mode']
            ] for s in symbols]
            
            print("\nAvailable MT5 Symbols:")
            print(tabulate(rows, headers=headers, tablefmt='grid'))
            print(f"\nTotal symbols: {len(symbols)}")
        else:
            print("No symbols found matching the filter.")
    
    # Show current mappings unless we're just listing MT5 symbols
    if not args.mt5_symbols:
        print("\nCurrent symbol mappings:")
        print("-" * 30)
        for tv_symbol, mt5_symbol in symbol_mapper.get_all_mappings().items():
            print(f"{tv_symbol:<15} -> {mt5_symbol}")
        print(f"\nDefault suffix: {symbol_mapper.suffix}")
    
    # Cleanup MT5
    if args.mt5_symbols:
        mt5.shutdown()

if __name__ == "__main__":
    main()