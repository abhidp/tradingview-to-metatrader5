import sys
from pathlib import Path
import logging
import signal
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('tradingview_copier.log')
    ]
)

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mitmproxy import ctx
from src.core.interceptor import TradingViewInterceptor

# Create logger
logger = logging.getLogger('ProxyServer')
logger.setLevel(logging.INFO)

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("\n⛔ Shutdown requested...")
    
    # Cleanup if interceptor has cleanup method
    if hasattr(addons[0], 'cleanup'):
        addons[0].cleanup()
    
    logger.info("Cleanup completed")
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

print("\nTradingView Proxy Server")
print("======================")
print("Starting proxy server...")
print("Listening for trades...")
print("Press Ctrl+C to stop\n")

# Don't silence mitmproxy
ctx.log.silent = False
ctx.options.flow_detail = 0
ctx.options.termlog_verbosity = 'error'

print("\n🚀 Proxy Server Started")
print("Watching for trades...\n")

# Initialize interceptor and add to addons
addons = [TradingViewInterceptor()]