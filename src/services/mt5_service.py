import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class MT5Service:
    """Service to handle MT5 operations."""
    
    def __init__(self, account: int, password: str, server: str):
        self.account = account
        self.password = password
        self.server = server
        self.initialized = False
        self.setup_logging()
        
    def setup_logging(self):
        """Setup service logging."""
        self.logger = logging.getLogger('MT5Service')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler('logs/mt5_service.log')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def initialize(self) -> bool:
        """Initialize MT5 connection."""
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        except ImportError as e:
            self.logger.error(f"Failed to import MetaTrader5: {e}")
            return False
            
        if self.initialized:
            return True
            
        try:
            # Check if MT5 terminal is installed
            terminal_path = self.find_mt5_terminal()
            if not terminal_path:
                self.logger.error("MT5 terminal not found")
                return False
                
            # Initialize MT5
            if not self.mt5.initialize(
                path=str(terminal_path),
                login=self.account,
                password=self.password,
                server=self.server
            ):
                error = self.mt5.last_error()
                self.logger.error(f"MT5 initialization failed: {error}")
                return False
                
            self.initialized = True
            self.logger.info("MT5 initialized successfully")
            
            # Log account info
            account_info = self.mt5.account_info()
            if account_info is not None:
                self.logger.info(f"Connected to account: {account_info.login} ({account_info.server})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing MT5: {e}")
            return False

    def find_mt5_terminal(self) -> Optional[Path]:
        """Find MT5 terminal installation path."""
        possible_paths = [
            Path("C:/Program Files/ICMarkets - MetaTrader 5/terminal64.exe"),
            Path("C:/Program Files (x86)/ICMarkets - MetaTrader 5/terminal.exe"),
            # Add other possible paths if needed
        ]
        
        for path in possible_paths:
            if path.exists():
                self.logger.info(f"Found MT5 terminal at: {path}")
                return path
                
        return None
    
    def execute_market_order(self, symbol: str, volume: float, order_type: str, 
                           deviation: int = 20) -> Dict[str, Any]:
        """Execute market order on MT5."""
        if not self.initialize():
            return {"error": "MT5 initialization failed"}
            
        try:
            # Normalize order type
            action = self.mt5.TRADE_ACTION_DEAL
            order_type = order_type.lower()
            type = self.mt5.ORDER_TYPE_BUY if order_type == "buy" else self.mt5.ORDER_TYPE_SELL
            
            # Get current price
            tick = self.mt5.symbol_info_tick(symbol)
            if not tick:
                return {"error": f"Failed to get price for {symbol}"}
                
            price = tick.ask if type == self.mt5.ORDER_TYPE_BUY else tick.bid
            
            # Enable symbol for trading if needed
            if not self.mt5.symbol_select(symbol, True):
                return {"error": f"Failed to select symbol {symbol}"}
            
            # Get symbol info
            symbol_info = self.mt5.symbol_info(symbol)
            if symbol_info is None:
                return {"error": f"Failed to get symbol info for {symbol}"}
            
            # Prepare the request
            request = {
                "action": action,
                "symbol": symbol,
                "volume": volume,
                "type": type,
                "price": price,
                "deviation": deviation,
                "magic": 234000,
                "comment": "python-trade",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
            
            # Send the order
            result = self.mt5.order_send(request)
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                error_msg = f"Order failed: {result.comment}"
                self.logger.error(error_msg)
                return {"error": error_msg}
            
            # Return success response
            response = {
                "ticket": result.order,
                "volume": result.volume,
                "price": result.price,
                "comment": result.comment,
                "request": request,
                "timestamp": datetime.now().isoformat()
            }
            self.logger.info(f"Order executed successfully: {response}")
            return response
            
        except Exception as e:
            error_msg = f"Error executing order: {e}"
            self.logger.error(error_msg)
            return {"error": error_msg}
    
    def shutdown(self):
        """Shutdown MT5 connection."""
        if self.initialized:
            try:
                self.mt5.shutdown()
                self.initialized = False
                self.logger.info("MT5 connection shutdown")
            except Exception as e:
                self.logger.error(f"Error shutting down MT5: {e}")