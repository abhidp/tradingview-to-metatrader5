import os
import time
from datetime import datetime

class StatusDisplay:
    def __init__(self):
        self.last_update = datetime.now()
        self.trade_count = 0
        self.last_trade = None
    
    def update(self, message=None):
        """Update the status display."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("\nTrading View Proxy Status")
        print("=====================")
        print(f"Running since: {self.last_update.strftime('%H:%M:%S')}")
        print(f"Trades intercepted: {self.trade_count}")
        if self.last_trade:
            print(f"Last trade: {self.last_trade}")
        if message:
            print(f"\nLast Event: {message}")
        print("\nPress Ctrl+C to stop")