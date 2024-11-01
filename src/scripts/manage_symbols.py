import sys
from pathlib import Path
import argparse

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.utils.symbol_mapper import SymbolMapper

def main():
    parser = argparse.ArgumentParser(description='Symbol Mapping Management')
    parser.add_argument('--filter', '-f', help='Filter symbols (e.g., "USD")')
    parser.add_argument('--refresh', '-r', action='store_true', help='Refresh from MT5')
    parser.add_argument('--add', '-a', nargs=2, metavar=('TV_SYMBOL', 'MT5_SYMBOL'), 
                       help='Add new mapping')
    parser.add_argument('--remove', '-d', metavar='TV_SYMBOL',
                       help='Remove mapping')
    
    args = parser.parse_args()
    
    mapper = SymbolMapper()
    
    if args.add:
        mapper.add_mapping(args.add[0].upper(), args.add[1])
        return
        
    if args.remove:
        mapper.remove_mapping(args.remove.upper())
        return
    
    if args.refresh:
        mapper.refresh_mappings()
    
    # Display mappings
    mappings = mapper.mappings
    if args.filter:
        filter_str = args.filter.upper()
        mappings = {k: v for k, v in mappings.items() if filter_str in k}
    
    print("\nSymbol Mappings:")
    print("-" * 30)
    for tv_symbol, mt5_symbol in sorted(mappings.items()):
        print(f"{tv_symbol:12} → {mt5_symbol}")

if __name__ == "__main__":
    main()