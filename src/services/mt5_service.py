import MetaTrader5 as mt5
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import time
import json

logger = logging.getLogger('MT5Service')

class MT5Service:
    def __init__(self, account: int, password: str, server: str):
        self.account = account
        self.password = password
        self.server = server
        self.initialized = False
        self.last_init_time = 0
        self.init_cooldown = 1  # seconds between initialization attempts
        
        # Symbol mapping
        self.symbol_map = {
            'BTCUSD': 'BTCUSD.a',
            'ETHUSD': 'ETHUSD.a',
            'XAUUSD': 'XAUUSD.a'
        }
    
    def initialize(self) -> bool:
        """Initialize MT5 connection with cooldown."""
        try:
            # Check if we've tried initialization recently
            current_time = time.time()
            if current_time - self.last_init_time < self.init_cooldown:
                time.sleep(self.init_cooldown)
            
            # If already initialized, check connection
            if self.initialized:
                if mt5.account_info() is not None:
                    return True
                self.initialized = False
            
            # Initialize MT5
            if not mt5.initialize():
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
            
            # Login to account
            if not mt5.login(self.account, password=self.password, server=self.server):
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            # Verify connection
            account_info = mt5.account_info()
            if not account_info:
                logger.error("Could not get account info")
                mt5.shutdown()
                return False
            
            self.initialized = True
            self.last_init_time = current_time
            
            logger.info(f"MT5 initialized successfully (Account: {account_info.login})")
            print(f"\n✅ Connected to MT5:")
            print(f"Account: {account_info.login}")
            print(f"Balance: {account_info.balance} {account_info.currency}")
            print(f"Leverage: 1:{account_info.leverage}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing MT5: {e}")
            self.initialized = False
            return False
    
    def map_symbol(self, tv_symbol: str) -> str:
        """Map TradingView symbol to MT5 symbol."""
        return self.symbol_map.get(tv_symbol, f"{tv_symbol}.a")
    
    def execute_market_order(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute market order on MT5."""
        try:
            if not self.initialize():
                return {"error": "MT5 initialization failed"}
            
            # Extract trade details
            print("\n🔍 Trade data received:")
            print(json.dumps(trade_data, indent=2))

            # Get required fields from either direct fields or execution_data
            execution_data = trade_data.get('execution_data', {})
            
            instrument = trade_data.get('instrument') or execution_data.get('instrument')
            side = trade_data.get('side') or execution_data.get('side')
            qty = trade_data.get('qty') or execution_data.get('qty')
            
            if not all([instrument, side, qty]):
                return {"error": f"Missing required fields. Got: instrument={instrument}, side={side}, qty={qty}"}

            # Map symbol
            mt5_symbol = self.map_symbol(instrument)
            
            # Enable symbol for trading
            retries = 3
            for attempt in range(retries):
                if mt5.symbol_select(mt5_symbol, True):
                    break
                if attempt == retries - 1:
                    return {"error": f"Failed to select symbol {mt5_symbol}"}
                time.sleep(1)  # Wait before retry
            
            # Get symbol info
            symbol_info = mt5.symbol_info(mt5_symbol)
            if not symbol_info:
                return {"error": f"Failed to get symbol info for {mt5_symbol}"}
            
            # Determine order type and price
            is_buy = side.lower() == 'buy'
            order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            price = symbol_info.ask if is_buy else symbol_info.bid
            
            # Remove 'TV_' prefix if it exists
            comment = trade_data.get('trade_id', 'trade')
            if comment.startswith('TV_'):
                comment = comment[3:]
            
            # Prepare request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": mt5_symbol,
                "volume": float(qty),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            logger.info(f"Sending order: {request}")
            
            # Execute trade
            result = mt5.order_send(request)
            if not result:
                return {"error": f"Order failed: {mt5.last_error()}"}
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    "error": f"Order failed: {result.comment}",
                    "retcode": result.retcode
                }
            
            # Format response
            response = {
                "mt5_ticket": str(result.order),
                "mt5_position": str(result.order),  # In MT5, the position ticket is same as the order ticket
                "volume": result.volume,
                "price": result.price,
                "symbol": mt5_symbol,
                "side": side,
                "comment": result.comment,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Order executed successfully: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Error executing order: {e}")
            return {"error": str(e)}

    def close_position(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Close an existing position."""
        try:
            print("\n🔍 Close position data received:")
            print(json.dumps(trade_data, indent=2))
            
            if not self.initialize():
                return {"error": "MT5 initialization failed"}

            # Extract required fields
            mt5_ticket = trade_data.get('mt5_ticket')
            if not mt5_ticket:
                return {"error": "MT5 ticket not provided"}

            # Get instrument from either direct fields or execution_data
            execution_data = trade_data.get('execution_data', {})
            instrument = trade_data.get('instrument') or execution_data.get('instrument')
            qty = trade_data.get('qty') or execution_data.get('qty')

            if not instrument:
                return {"error": "Instrument not provided"}
            if not qty:
                return {"error": "Quantity not provided"}

            # Map symbol
            mt5_symbol = self.map_symbol(instrument)
            
            print(f"\n📊 Close request details:")
            print(f"MT5 Ticket: {mt5_ticket}")
            print(f"Symbol: {mt5_symbol}")
            print(f"Quantity: {qty}")
            
            # Enable symbol for trading
            retries = 3
            for attempt in range(retries):
                if mt5.symbol_select(mt5_symbol, True):
                    break
                if attempt == retries - 1:
                    return {"error": f"Failed to select symbol {mt5_symbol}"}
                time.sleep(1)

            # Get symbol info
            symbol_info = mt5.symbol_info(mt5_symbol)
            if not symbol_info:
                return {"error": f"Failed to get symbol info for {mt5_symbol}"}

            # Find position to close
            positions = mt5.positions_get(ticket=int(mt5_ticket))
            if not positions:
                return {"error": f"No position found with ticket {mt5_ticket}"}

            position = positions[0]

            # Determine closing details
            is_buy = position.type == mt5.POSITION_TYPE_SELL  # Reverse for closing
            order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            price = symbol_info.ask if is_buy else symbol_info.bid

            # Prepare comment (remove TV_ prefix if present)
            comment = trade_data.get('trade_id', 'trade')
            if comment.startswith('TV_'):
                comment = comment[3:]

            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": mt5_symbol,
                "volume": float(qty),
                "type": order_type,
                "position": int(mt5_ticket),
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": comment,  # Using cleaned comment
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            logger.info(f"Sending close request: {request}")

            # Execute close
            result = mt5.order_send(request)
            if not result:
                return {"error": f"Close order failed: {mt5.last_error()}"}

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    "error": f"Close order failed: {result.comment}",
                    "retcode": result.retcode
                }

            # Format response
            response = {
                "mt5_ticket": str(result.order),
                "volume": result.volume,
                "price": result.price,
                "symbol": mt5_symbol,
                "side": "buy" if is_buy else "sell",
                "comment": result.comment,
                "closed_position": str(position.ticket),
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Position closed successfully: {response}")
            return response

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"error": str(e)}
        
    def cleanup(self):
        """Cleanup connection."""
        if self.initialized:
            mt5.shutdown()
            self.initialized = False