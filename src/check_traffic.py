import requests
import logging
from urllib3.exceptions import InsecureRequestWarning
import time
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TrafficCheck')

def test_proxy():
    """Test if proxy is intercepting HTTPS traffic."""
    proxies = {
        'http': 'http://127.0.0.1:8080',
        'https': 'http://127.0.0.1:8080'
    }
    
    # Test 1: Basic proxy check
    try:
        logger.info("\nTest 1: Basic proxy check")
        response = requests.get('https://www.tradingview.com', proxies=proxies, verify=False)
        logger.info(f"TradingView Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Proxy check failed: {e}")
        return

    # Test 2: ICMarkets with proper headers
    try:
        logger.info("\nTest 2: ICMarkets API check")
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://www.tradingview.com',
            'pragma': 'no-cache',
            'referer': 'https://www.tradingview.com/',
            'sec-ch-ua': '"Chromium";v="118"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        }
        
        response = requests.get(
            'https://icmarkets.tv.ctrader.com/config?locale=en',
            headers=headers,
            proxies=proxies,
            verify=False
        )
        logger.info(f"ICMarkets Config Status: {response.status_code}")
        if response.status_code == 200:
            logger.info(f"Response: {response.json()}")
    except Exception as e:
        logger.error(f"ICMarkets check failed: {e}")

    # Test 3: Monitor live traffic
    logger.info("\nTest 3: Monitoring trading requests")
    logger.info("Please perform these steps:")
    logger.info("1. Open TradingView in your browser")
    logger.info("2. Log in to your account")
    logger.info("3. Open a chart")
    logger.info("4. Place a test trade")
    logger.info("\nMonitoring for 60 seconds...")
    
    start_time = time.time()
    while time.time() - start_time < 60:
        try:
            response = requests.get(
                'https://icmarkets.tv.ctrader.com/accounts/40807470/state?locale=en',
                headers=headers,
                proxies=proxies,
                verify=False
            )
            if response.status_code == 200:
                logger.info(f"Successfully captured traffic at {time.strftime('%H:%M:%S')}")
            time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
            time.sleep(1)

if __name__ == "__main__":
    test_proxy()