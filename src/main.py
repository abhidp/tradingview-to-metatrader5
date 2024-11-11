import sys
from pathlib import Path
import logging
import argparse
# from mitmproxy import ctx

# Configure logging to be minimal
logging.basicConfig(
    level=logging.ERROR,  # Only show errors
    format='%(message)s',  # Simplified format
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('tradingview_copier.log', mode='a')
    ]
)

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.interceptor import TradingViewInterceptor

# Add the interceptor to mitmproxy
addons = [TradingViewInterceptor()]