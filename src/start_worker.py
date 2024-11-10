import os
import sys
import signal
import logging
from pathlib import Path
import atexit

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from src.workers.mt5_worker import MT5Worker
from src.utils.ssl_handler import silence_ssl_warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('WorkerMain')

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
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
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Silence SSL warnings
    silence_ssl_warnings()
    
    worker = MT5Worker()
    try:
        worker.run()
    except KeyboardInterrupt:
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

if __name__ == "__main__":
    main()