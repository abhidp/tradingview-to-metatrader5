from pathlib import Path
import os

# Base paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
LOGS_DIR = PROJECT_ROOT / 'logs'
TRADES_DIR = LOGS_DIR / 'trades'

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
TRADES_DIR.mkdir(exist_ok=True)

# Logging settings
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'CRITICAL'  # Suppress most logs

# Trade data settings
TRADE_FILE_PREFIX = 'trades_'