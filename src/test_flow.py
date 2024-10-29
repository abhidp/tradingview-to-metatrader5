import os
import sys
from pathlib import Path
import logging
import requests
from urllib3.exceptions import InsecureRequestWarning
import json

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TestFlow')

def test_proxy_connection():
    """Test if proxy is working."""
    try:
        proxies = {
            'http': 'http://127.0.0.1:8080',
            'https': 'http://127.0.0.1:8080'
        }
        
        response = requests.get('https://api.ipify.org?format=json', 
                              proxies=proxies, 
                              verify=False)
        logger.info(f"Proxy test response: {response.text}")
        return True
    except Exception as e:
        logger.error(f"Proxy test failed: {e}")
        return False

def simulate_trade_request():
    """Simulate a trade request through the proxy."""
    try:
        proxies = {
            'http': 'http://127.0.0.1:8080',
            'https': 'http://127.0.0.1:8080'
        }
        
        # Trade data
        trade_data = {
            'instrument': 'BTCUSD',
            'side': 'buy',
            'qty': '0.01',
            'type': 'market',
            'currentAsk': '68000.00',
            'currentBid': '67990.00',
            'locale': 'en'
        }
        
        # Headers similar to TradingView
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Authorization': 'Bearer PUT_YOUR_BEARER_TOKEN_HERE'  # We need the actual token
        }
        
        # Make request
        url = f'https://icmarkets.tv.ctrader.com/accounts/40807470/orders?locale=en'
        
        logger.info(f"Making request to: {url}")
        logger.info(f"Headers: {headers}")
        logger.info(f"Data: {trade_data}")
        
        response = requests.post(url, 
                               data=trade_data, 
                               headers=headers, 
                               proxies=proxies, 
                               verify=False)
        
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Body: {response.text}")
        return True
    except Exception as e:
        logger.error(f"Trade simulation failed: {e}")
        return False

def main():
    logger.info("Testing proxy and trade flow...")
    
    if not test_proxy_connection():
        logger.error("Proxy connection test failed!")
        return
    
    logger.info("\nProxy is working correctly.")
    logger.info("To capture the actual request format and auth token:")
    logger.info("1. Place a trade in TradingView")
    logger.info("2. Check the proxy server logs for the request details")
    logger.info("3. Copy those details into the test script")
    
    # Ask for confirmation before simulating trade
    confirm = input("\nDo you want to simulate a trade request? (y/n): ")
    if confirm.lower() == 'y':
        if simulate_trade_request():
            logger.info("Trade simulation completed successfully")
        else:
            logger.error("Trade simulation failed!")

if __name__ == "__main__":
    main()