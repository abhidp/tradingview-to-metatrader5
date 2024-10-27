from mitmproxy import ctx, http
import json
from datetime import datetime
from pathlib import Path
import logging
import sys
import builtins
import os

# Suppress all output except our specific trade messages
original_print = builtins.print
def custom_print(*args, **kwargs):
    if args and isinstance(args[0], str) and (args[0].startswith("🚀") or args[0].startswith("\n📊")):
        original_print(*args, **kwargs)

builtins.print = custom_print

# Completely suppress mitmproxy output
ctx.log.silent = True
logging.getLogger('mitmproxy').setLevel(logging.CRITICAL)
logging.getLogger('mitmdump').setLevel(logging.CRITICAL)

def setup_logging():
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    file_handler = logging.FileHandler(log_dir / f'proxy_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.CRITICAL)
    
    return log_dir

BASE_URL = 'icmarkets.tv.ctrader.com/accounts/40807470/orders'

class TradingViewInterceptor:
    def __init__(self):
        self.log_dir = setup_logging()
        self.trades_dir = self.log_dir / 'trades'
        self.trades_dir.mkdir(exist_ok=True)
        
        self.session_file = self.trades_dir / f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Initialize the JSON file with an empty array
        with open(self.session_file, 'w', encoding='utf-8') as f:
            f.write('[\n')  # Start the JSON array
        
        self.is_first_trade = True
        
        original_print("\n🚀 Trade capture proxy server started")
        original_print("Monitoring for trade executions...\n")

    def is_trade_execution(self, flow: http.HTTPFlow) -> bool:
        """Strictly check if the request is a trade execution."""
        return (BASE_URL in flow.request.pretty_url and 
                flow.request.method == "POST" and
                flow.request.urlencoded_form and
                all(key in flow.request.urlencoded_form for key in ['instrument', 'side', 'qty']))

    def extract_trade_data(self, flow: http.HTTPFlow) -> dict:
        """Extract relevant trade data from the request."""
        try:
            form_data = dict(flow.request.urlencoded_form)
            
            response_data = None
            if flow.response and flow.response.content:
                try:
                    response_data = json.loads(flow.response.content.decode('utf-8'))
                except:
                    response_data = "<Unable to parse response>"
            
            return {
                'timestamp': datetime.now().isoformat(),
                'request_data': form_data,
                'response': response_data
            }
            
        except Exception:
            return None

    def log_trade(self, trade_data: dict):
        """Log trade data to JSON file and console."""
        try:
            # Format the trade data as JSON with indentation
            json_str = json.dumps(trade_data, indent=2)
            
            # Write to file with proper JSON array formatting
            with open(self.session_file, 'a', encoding='utf-8') as f:
                if not self.is_first_trade:
                    f.write(',\n')  # Add comma and newline before new trade
                f.write(json_str)  # Write the trade data
                self.is_first_trade = False
            
            # Print trade info
            request_data = trade_data['request_data']
            original_print("\n📊 Trade Executed:")
            original_print(f"Instrument: {request_data.get('instrument', 'N/A')}")
            original_print(f"Side: {request_data.get('side', 'N/A')}")
            original_print(f"Quantity: {request_data.get('qty', 'N/A')}")
            original_print(f"Type: {request_data.get('type', 'N/A')}")
            original_print("-" * 40)
                
        except Exception:
            pass

    def response(self, flow: http.HTTPFlow) -> None:
        """Process only trade execution responses."""
        if self.is_trade_execution(flow):
            trade_data = self.extract_trade_data(flow)
            if trade_data:
                self.log_trade(trade_data)

    def done(self):
        """Clean up when the proxy is shutdown."""
        try:
            # Close the JSON array
            with open(self.session_file, 'a', encoding='utf-8') as f:
                f.write('\n]')
        except Exception:
            pass

addons = [TradingViewInterceptor()]