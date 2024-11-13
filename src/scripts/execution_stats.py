import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from src.utils.database_handler import DatabaseHandler


def main():
    db = DatabaseHandler()
    
    print("\n📊 Execution Time Statistics")
    
    print("\nLast 100 trades:")
    stats = db.get_execution_stats(limit=100)
    if stats['count'] > 0:
        print(f"Count  : {stats['count']} trades")
        print(f"Average: {stats['avg_ms']:.2f}ms")
        print(f"Minimum: {stats['min_ms']}ms")
        print(f"Maximum: {stats['max_ms']}ms")
    else:
        print("No trades found")
    
    print("\nLast 24 hours:")
    stats = db.get_execution_stats(days=1)
    if stats['count'] > 0:
        print(f"Count  : {stats['count']} trades")
        print(f"Average: {stats['avg_ms']:.2f}ms")
    else:
        print("No trades in last 24 hours")

if __name__ == "__main__":
    print("\n=== Trade Execution Statistics ===")
    main()
    print("\nDone!")