import logging
import builtins
from datetime import datetime
from pathlib import Path
from src.config.settings import LOGS_DIR, LOG_FORMAT, LOG_LEVEL

# Store original print function
original_print = builtins.print

def custom_print(*args, **kwargs):
    """Custom print function that only prints trade-related messages."""
    if args and isinstance(args[0], str) and (args[0].startswith("🚀") or args[0].startswith("\n📊")):
        original_print(*args, **kwargs)

def setup_logging():
    """Configure logging settings."""
    # Clear all existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Only log to file
    log_file = LOGS_DIR / f'proxy_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Override print function
    builtins.print = custom_print
    
    return log_file