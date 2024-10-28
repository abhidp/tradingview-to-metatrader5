import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mitmproxy import ctx
import logging
from src.utils.logging import setup_logging
from src.core.interceptor import TradingViewInterceptor

# Suppress mitmproxy output
ctx.log.silent = True
logging.getLogger('mitmproxy').setLevel(logging.CRITICAL)
logging.getLogger('mitmdump').setLevel(logging.CRITICAL)

# Setup logging
setup_logging()

# Create interceptor instance
addons = [TradingViewInterceptor()]