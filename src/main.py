import sys
from pathlib import Path
import logging

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mitmproxy import ctx
from src.core.interceptor import TradingViewInterceptor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Create logger
logger = logging.getLogger('ProxyServer')
logger.setLevel(logging.INFO)

print("\n🚀 Proxy Server Started")
print("Watching for trades...\n")

# Don't silence mitmproxy
ctx.log.silent = False
ctx.options.flow_detail = 0
ctx.options.termlog_verbosity  = 'error'


addons = [TradingViewInterceptor()]