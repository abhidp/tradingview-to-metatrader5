import os
import sys
from pathlib import Path
import time
import logging
from datetime import datetime

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.queue_handler import RedisQueue
from src.services.trade_executor import TradeExecutor
from src.utils.database_handler import DatabaseHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Monitor')

class TradeMonitor:
    def __init__(self):
        self.queue = RedisQueue()
        self.db = DatabaseHandler()
        self.executor = TradeExecutor()
        self.running = True
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_status(self, status: dict, trades: list, account_info: dict):
        """Print current status."""
        self.clear_screen()
        
        print("\n📊 Trade Monitor")
        print("==============")
        
        # Queue Status
        print("\nQueue Status:")
        print(f"Pending   : {status['pending']}")
        print(f"Processing: {status['processing']}")
        print(f"Completed : {status['completed']}")
        print(f"Failed    : {status['failed']}")
        
        # Recent Trades
        print("\nRecent Trades:")
        if trades:
            for trade in trades:
                print(f"\n{trade['timestamp']}")
                print(f"{trade['instrument']} - {trade['side']} {trade['quantity']}")
                print(f"Status: {trade['status']}")
        else:
            print("No recent trades")
        
        # MT5 Account Status
        if 'error' not in account_info:
            print("\nMT5 Account:")
            if 'account' in account_info:
                acc = account_info['account']
                print(f"Balance: {acc.get('balance')} {acc.get('currency', '')}")
                print(f"Equity : {acc.get('equity')} {acc.get('currency', '')}")
        
        print("\nPress Ctrl+C to stop monitoring")
        print(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
    
    def run(self):
        """Run the monitor."""
        print("\n📊 Starting Trade Monitor...")
        
        while self.running:
            try:
                # Get current status
                status = self.queue.get_queue_status()
                trades = self.db.get_recent_trades(5)
                account_info = self.executor.verify_account()
                
                # Update display
                self.print_status(status, trades, account_info)
                
                # Wait before next update
                time.sleep(2)
                
            except KeyboardInterrupt:
                print("\nShutdown requested...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in monitor: {e}", exc_info=True)
                time.sleep(5)  # Longer delay on error

def main():
    monitor = TradeMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        print("\nMonitor stopped")

if __name__ == "__main__":
    main()