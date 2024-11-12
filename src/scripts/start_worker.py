import os
import sys
import signal
import logging
from pathlib import Path
import atexit

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)  # One more parent to reach root
sys.path.insert(0, project_root)

from src.workers.mt5_worker import MT5Worker
from src.utils.ssl_handler import silence_ssl_warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('WorkerMain')

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Print worker banner."""
    print("\nMT5 Trade Worker")
    print("================")
    print("Starting worker...")
    print("Press Ctrl+C to stop\n")

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    print("\n⛔ Shutdown requested...")
    logger.info("Received termination signal. Initiating shutdown...")
    sys.exit(0)

def cleanup():
    """Cleanup function to be called on exit."""
    logger.info("Performing final cleanup...")
    try:
        # Add any additional cleanup tasks here
        pass
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        logger.info("Cleanup completed.")
        # Force exit if still hanging
        os._exit(0)

def main():
    try:
        # Clear screen and show banner
        clear_screen()
        print_banner()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Register cleanup function
        atexit.register(cleanup)
        
        # Silence SSL warnings
        silence_ssl_warnings()
        
        # Initialize and start worker
        worker = MT5Worker()
        try:
            worker.run()
        except KeyboardInterrupt:
            print("\n⛔ Shutdown requested by user...")
            logger.info("Shutdown requested via keyboard interrupt...")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            try:
                worker.cleanup()
                logger.info("Worker stopped normally.")
            except Exception as e:
                logger.error(f"Error during worker cleanup: {e}")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error during startup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()