import logging
import MetaTrader5 as mt5
from datetime import datetime
from typing import Dict, Any, Optional
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.symbol_mapper import SymbolMapper

class TradeExecutor:
    """Handles trade execution in MT5."""
    
    def __init__(self, symbol_mapper: SymbolMapper = None):
        self.logger = logging.getLogger('TradeExecutor')
        self.symbol_mapper = symbol_mapper or SymbolMapper()
        
    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection."""
        if not mt5.initialize():
            self.logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        return True
    
    def verify_account(self) -> Dict[str, Any]:
        """Verify MT5 account status."""
        try:
            if not self.initialize_mt5():
                return {"error": "MT5 initialization failed"}
            
            # Get account info
            account_info = mt5.account_info()
            if account_info is None:
                return {"error": "Failed to get account info"}
            
            # Get terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                return {"error": "Failed to get terminal info"}
            
            # Format account info
            account_details = {
                "login": account_info.login,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "margin": account_info.margin,
                "free_margin": account_info.margin_free,
                "leverage": f"1:{account_info.leverage}",
                "currency": account_info.currency,
            }
            
            # Add terminal status
            terminal_details = {
                "connected": terminal_info.connected,
                "trade_allowed": terminal_info.trade_allowed,
                "company": terminal_info.company,
                "path": terminal_info.path,
                "platform": "MT5",
                "version": mt5.version()
            }
            
            # Combine all info
            return {
                "account": account_details,
                "terminal": terminal_details,
                "status": "connected" if terminal_info.connected else "disconnected",
                "trading_enabled": terminal_info.trade_allowed
            }
            
        except Exception as e:
            self.logger.error(f"Error verifying account: {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            mt5.shutdown()
            
    def get_symbol_info(self, tv_symbol: str) -> Dict[str, Any]:
        """Get symbol information."""
        try:
            if not self.initialize_mt5():
                return {"error": "MT5 initialization failed"}
            
            mt5_symbol = self.symbol_mapper.get_mt5_symbol(tv_symbol)
            
            if not mt5.symbol_select(mt5_symbol, True):
                return {"error": f"Failed to select symbol {mt5_symbol}"}
            
            symbol_info = mt5.symbol_info(mt5_symbol)
            if symbol_info is None:
                return {"error": f"Failed to get symbol info for {mt5_symbol}"}
            
            return {
                "symbol": mt5_symbol,
                "bid": symbol_info.bid,
                "ask": symbol_info.ask,
                "spread": symbol_info.spread,
                "digits": symbol_info.digits,
                "min_lot": symbol_info.volume_min,
                "max_lot": symbol_info.volume_max,
                "lot_step": symbol_info.volume_step,
                "point": symbol_info.point
            }
            
        except Exception as e:
            return {"error": str(e)}
        finally:
            mt5.shutdown()
    
    def execute_market_order(self, trade_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a market order in MT5."""
        try:
            if not self.initialize_mt5():
                return {"error": "MT5 initialization failed"}
            
            # Map the symbol
            tv_symbol = trade_request['instrument']
            mt5_symbol = self.symbol_mapper.get_mt5_symbol(tv_symbol)
            
            # Enable symbol for trading
            if not mt5.symbol_select(mt5_symbol, True):
                return {"error": f"Failed to select symbol {mt5_symbol}"}
            
            # Get symbol info
            symbol_info = mt5.symbol_info(mt5_symbol)
            if symbol_info is None:
                return {"error": f"Failed to get symbol info for {mt5_symbol}"}
            
            # Determine order type
            order_type = mt5.ORDER_TYPE_BUY if trade_request['side'].lower() == 'buy' else mt5.ORDER_TYPE_SELL
            price = symbol_info.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_info.bid
            
            # Prepare the request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": mt5_symbol,
                "volume": float(trade_request['qty']),
                "type": order_type,
                "price": price,
                "deviation": 20,  # Maximum price deviation in points
                "magic": 234000,  # Magic number to identify our trades
                "comment": f"TV_{trade_request.get('requestId', 'trade')}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Log the request
            self.logger.info(f"Sending order: {request}")
            
            # Execute the trade
            result = mt5.order_send(request)
            if result is None:
                return {"error": f"order_send() failed: {mt5.last_error()}"}
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    "error": f"Order failed: {result.comment}",
                    "retcode": result.retcode,
                    "request": request
                }
            
            # Format successful result
            response = {
                "order_id": str(result.order),
                "volume": result.volume,
                "price": result.price,
                "comment": result.comment,
                "symbol": mt5_symbol,
                "type": "buy" if order_type == mt5.ORDER_TYPE_BUY else "sell",
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.info(f"Order executed successfully: {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}", exc_info=True)
            return {"error": str(e)}
        
        finally:
            mt5.shutdown()

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get open position for a symbol."""
        try:
            if not self.initialize_mt5():
                return None
                
            mt5_symbol = self.symbol_mapper.get_mt5_symbol(symbol)
            positions = mt5.positions_get(symbol=mt5_symbol)
            
            if positions is None or len(positions) == 0:
                return None
                
            # Return the first position found
            pos = positions[0]._asdict()
            return {
                "ticket": pos['ticket'],
                "symbol": pos['symbol'],
                "type": "buy" if pos['type'] == mt5.POSITION_TYPE_BUY else "sell",
                "volume": pos['volume'],
                "price_open": pos['price_open'],
                "price_current": pos['price_current'],
                "profit": pos['profit']
            }
            
        except Exception as e:
            self.logger.error(f"Error getting position: {e}")
            return None
        finally:
            mt5.shutdown()
    
    def close_position(self, symbol: str, ticket: Optional[int] = None) -> Dict[str, Any]:
        """Close an open position."""
        try:
            if not self.initialize_mt5():
                return {"error": "MT5 initialization failed"}
                
            mt5_symbol = self.symbol_mapper.get_mt5_symbol(symbol)
            
            # Get position
            if ticket:
                positions = mt5.positions_get(ticket=ticket)
            else:
                positions = mt5.positions_get(symbol=mt5_symbol)
                
            if not positions:
                return {"error": f"No open position found for {symbol}"}
                
            position = positions[0]._asdict()
            
            # Determine closing details
            close_type = mt5.ORDER_TYPE_SELL if position['type'] == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(mt5_symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(mt5_symbol).ask
            
            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": mt5_symbol,
                "volume": position['volume'],
                "type": close_type,
                "position": position['ticket'],
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": f"Close_{position['ticket']}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            self.logger.info(f"Sending close request: {request}")
            
            # Execute close
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    "error": f"Close failed: {result.comment}",
                    "retcode": result.retcode
                }
            
            return {
                "success": True,
                "order_id": str(result.order),
                "volume": result.volume,
                "price": result.price,
                "comment": result.comment,
                "symbol": mt5_symbol,
                "type": "close",
                "ticket": position['ticket'],
                "profit": position['profit'],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return {"error": str(e)}
        finally:
            mt5.shutdown()