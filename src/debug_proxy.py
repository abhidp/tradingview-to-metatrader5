import os
import sys
from pathlib import Path
import logging
import requests
import time
from urllib3.exceptions import InsecureRequestWarning

# Suppress insecure warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ProxyDebug')

def test_proxy():
    """Test if proxy is working and intercepting traffic."""
    proxies = {
        'http': 'http://127.0.0.1:8080',
        'https': 'http://127.0.0.1:8080'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }
    
    urls_to_test = [
        'https://www.tradingview.com/chart/',
        'https://icmarkets.tv.ctrader.com/config?locale=en',
        'https://icmarkets.tv.ctrader.com/accounts/40807470/state?locale=en'
    ]
    
    print("\nTesting proxy connectivity...")
    for url in urls_to_test:
        try:
            response = requests.get(
                url, 
                proxies=proxies, 
                headers=headers,
                verify=False
            )
            print(f"\nTesting: {url}")
            print(f"Status: {response.status_code}")
            print(f"Content Type: {response.headers.get('content-type', 'N/A')}")
        except Exception as e:
            print(f"Error accessing {url}: {e}")
    
    print("\nStarting monitoring mode...")
    print("Place a trade in TradingView to see the intercepted traffic")
    print("Press Ctrl+C to stop monitoring\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    test_proxy()