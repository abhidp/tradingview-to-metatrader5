import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.workers.mt5_worker import MT5Worker
from src.services.trade_executor import TradeExecutor
from src.utils.symbol_mapper import SymbolMapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Worker')

class WorkerService:
    def __init__(self):
        self.running = True
        self.worker = None
        self.executor = None
        self.last_check = None
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\nShutdown requested...")
        self.running = False
        if self.worker:
            self.worker.running = False

    def print_status(self):
        """Print current status."""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\nMT5 Trade Worker")
        print("===============")
        print(f"Status: {'🟢 Running' if self.running else '🔴 Stopping'}")
        print(f"Last Check: {self.last_check.strftime('%H:%M:%S') if self.last_check else 'Never'}")
        
        if self.executor:
            account_info = self.executor.verify_account()
            if 'error' not in account_info:
                print("\nAccount Status:")
                if 'account' in account_info:
                    acc = account_info['account']
                    print(f"Balance: {acc.get('balance')} {acc.get('currency', '')}")
                    print(f"Equity: {acc.get('equity')} {acc.get('currency', '')}")
        
        print("\nPress Ctrl+C to stop")

    def initialize(self):
        """Initialize worker components."""
        try:
            self.executor = TradeExecutor(SymbolMapper())
            self.worker = MT5Worker()
            return True
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False

    def run(self):
        """Run the worker service."""
        if not self.initialize():
            logger.error("Failed to initialize worker")
            return

        print("\n🚀 Starting worker service...")
        
        try:
            while self.running:
                try:
                    self.last_check = datetime.now()
                    self.print_status()
                    
                    if not self.running:
                        break
                    
                    # Run one iteration of the worker
                    self.worker.run_once()
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error in worker loop: {e}")
                    time.sleep(1)
            
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources."""
        print("\nCleaning up...")
        if self.worker:
            self.worker.cleanup()
        if self.executor:
            self.executor.cleanup()
        print("Worker stopped")

def main():
    service = WorkerService()
    try:
        service.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        service.cleanup()

if __name__ == "__main__":
    main()