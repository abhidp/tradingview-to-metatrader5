import time
from datetime import datetime
import logging
from pathlib import Path
import sys
import os
import json

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.token_manager import GLOBAL_TOKEN_MANAGER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TokenMonitor')

def monitor_token_updates(duration_seconds=60):
    """Monitor token updates for a specified duration."""
    print(f"\nMonitoring token updates for {duration_seconds} seconds...")
    print("=" * 50)
    
    start_time = time.time()
    last_timestamp = None
    update_count = 0
    
    try:
        while time.time() - start_time < duration_seconds:
            info = GLOBAL_TOKEN_MANAGER.get_token_info()
            file_path = Path(info['file_path'])
            
            if file_path.exists():
                try:
                    data = json.loads(file_path.read_text())
                    current_timestamp = data.get('timestamp')
                    
                    if current_timestamp != last_timestamp:
                        update_count += 1
                        print(f"\nToken actually updated at {current_timestamp}")
                        print(f"File: {info['file_path']}")
                        print(f"Size: {info['file_size']} bytes")
                        last_timestamp = current_timestamp
                except Exception as e:
                    logger.error(f"Error reading token file: {e}")
            
            time.sleep(1)
        
        print("\nMonitoring Complete")
        print("=" * 50)
        if update_count > 0:
            print(f"Token was actually updated {update_count} times in {duration_seconds} seconds")
            print(f"Average updates per minute: {update_count / (duration_seconds/60):.2f}")
        else:
            print("No token updates detected - token is stable")
            if last_timestamp:
                print(f"Last update was at: {last_timestamp}")
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        logger.error(f"Error during monitoring: {e}")

if __name__ == '__main__':
    try:
        # Monitor for 1 minute by default
        monitor_token_updates(60)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        logger.error(f"Error during monitoring: {e}")