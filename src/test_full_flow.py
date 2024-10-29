import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FlowTest')

def test_database():
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname='tradingview',
            user='tvuser',
            password='tvpassword',
            host='localhost',
            port='5432'
        )
        conn.close()
        logger.info("✓ PostgreSQL connection successful")
        return True
    except Exception as e:
        logger.error(f"✗ PostgreSQL connection failed: {e}")
        return False

def test_redis():
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        logger.info("✓ Redis connection successful")
        return True
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False

def test_mt5():
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            raise Exception(mt5.last_error())
        
        # Get account info
        account_info = mt5.account_info()
        if account_info is None:
            raise Exception("Failed to get account info")
            
        logger.info(f"✓ MT5 connection successful (Account: {account_info.login})")
        logger.info(f"  Balance: {account_info.balance}")
        logger.info(f"  Equity: {account_info.equity}")
        
        mt5.shutdown()
        return True
    except Exception as e:
        logger.error(f"✗ MT5 connection failed: {e}")
        return False

def simulate_trade_flow():
    """Simulate the entire trade flow"""
    try:
        # Sample trade data
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "request_data": {
                "instrument": "BTCUSD.a",
                "side": "buy",
                "qty": 0.01,
                "type": "market",
                "currentAsk": 63000.00,
                "currentBid": 62990.00
            }
        }
        
        # 1. Store in PostgreSQL
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            dbname='tradingview',
            user='tvuser',
            password='tvpassword',
            host='localhost'
        )
        cur = conn.cursor()
        
        # Insert trade
        cur.execute("""
            INSERT INTO trades (
                timestamp, 
                instrument, 
                side, 
                quantity, 
                type, 
                current_ask,
                current_bid,
                request_data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            datetime.now(),
            trade_data['request_data']['instrument'],
            trade_data['request_data']['side'],
            trade_data['request_data']['qty'],
            trade_data['request_data']['type'],
            trade_data['request_data']['currentAsk'],
            trade_data['request_data']['currentBid'],
            json.dumps(trade_data)
        ))
        conn.commit()
        logger.info("✓ Trade stored in PostgreSQL")
        
        # 2. Push to Redis queue
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.lpush('trades:pending', json.dumps(trade_data))
        logger.info("✓ Trade pushed to Redis queue")
        
        # 3. Simulate MT5 execution
        import MetaTrader5 as mt5
        if not mt5.initialize():
            raise Exception("Failed to initialize MT5")
            
        symbol = trade_data['request_data']['instrument']
        volume = float(trade_data['request_data']['qty'])
        
        # Just check if we can get symbol info (don't actually place trade)
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning(f"Note: Symbol {symbol} not found in MT5")
        else:
            logger.info(f"✓ Symbol {symbol} found in MT5")
            logger.info(f"  Bid: {symbol_info.bid}, Ask: {symbol_info.ask}")
        
        # Verify queue status
        queue_length = r.llen('trades:pending')
        logger.info(f"✓ Redis queue length: {queue_length}")
        
        # Read back the trade from PostgreSQL
        cur.execute("SELECT * FROM trades ORDER BY created_at DESC LIMIT 1")
        trade_record = cur.fetchone()
        logger.info(f"✓ Trade record created with ID: {trade_record[0]}")
        
        mt5.shutdown()
        logger.info("✓ MT5 simulation successful")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Trade flow simulation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def main():
    logger.info("Starting full flow test...")
    logger.info(f"Python version: {sys.version}")
    
    # Test individual components
    db_ok = test_database()
    redis_ok = test_redis()
    mt5_ok = test_mt5()
    
    if all([db_ok, redis_ok, mt5_ok]):
        logger.info("\nAll components ready, testing full flow...")
        if simulate_trade_flow():
            logger.info("\n✓ Full flow test successful!")
        else:
            logger.error("\n✗ Full flow test failed!")
    else:
        logger.error("\n✗ Component tests failed!")

if __name__ == "__main__":
    main()