import os
import sys
import logging
import requests
import certifi
import ssl
from urllib3.exceptions import InsecureRequestWarning
from pathlib import Path

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('ProxyVerify')

def check_proxy_connection():
    """Test basic proxy connectivity."""
    try:
        proxies = {
            'http': 'http://127.0.0.1:8080',
            'https': 'http://127.0.0.1:8080'
        }
        
        logger.info("Testing proxy connection...")
        response = requests.get(
            'https://api.ipify.org?format=json',
            proxies=proxies,
            verify=False
        )
        logger.info(f"Proxy test response: {response.text}")
        return True
    except Exception as e:
        logger.error(f"Proxy connection test failed: {e}")
        return False

def check_tradingview_connection():
    """Test connection to TradingView through proxy."""
    try:
        proxies = {
            'http': 'http://127.0.0.1:8080',
            'https': 'http://127.0.0.1:8080'
        }
        
        urls_to_test = [
            'https://www.tradingview.com/chart/',
            'https://icmarkets.tv.ctrader.com/config?locale=en'
        ]
        
        logger.info("\nTesting TradingView connections...")
        for url in urls_to_test:
            logger.info(f"\nTesting {url}")
            response = requests.get(
                url,
                proxies=proxies,
                verify=False,
                allow_redirects=True
            )
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Headers: {dict(response.headers)}")
            
        return True
    except Exception as e:
        logger.error(f"TradingView connection test failed: {e}")
        return False

def check_certificate():
    """Check mitmproxy certificate."""
    cert_path = os.path.expanduser('~/.mitmproxy/mitmproxy-ca-cert.cer')
    
    logger.info("\nChecking mitmproxy certificate...")
    if os.path.exists(cert_path):
        logger.info(f"Certificate exists at: {cert_path}")
        
        # Try to load certificate
        try:
            context = ssl.create_default_context()
            context.load_verify_locations(cert_path)
            logger.info("Certificate loaded successfully")
        except Exception as e:
            logger.error(f"Certificate loading failed: {e}")
    else:
        logger.error("Certificate not found!")

def main():
    logger.info("Starting proxy verification...")
    
    # Check certificate
    check_certificate()
    
    # Check basic proxy
    if not check_proxy_connection():
        logger.error("Basic proxy check failed!")
        return
        
    # Check TradingView
    if not check_tradingview_connection():
        logger.error("TradingView connection check failed!")
        return
    
    logger.info("\nVerification complete!")
    
if __name__ == "__main__":
    main()