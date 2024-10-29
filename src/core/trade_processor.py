import logging
from typing import Dict, Any
from datetime import datetime
from src.services.trade_executor import TradeExecutor
from src.utils.symbol_mapper import SymbolMapper
from src.utils.queue_handler import RedisQueue

class TradeProcessor:
    """Processes trades from TradingView and executes them on MT5."""
    
    def __init__(self):
        self.logger = logging.getLogger('TradeProcessor')
        self.executor = TradeExecutor(SymbolMapper())
        self.queue = RedisQueue()
        
    def process_trade_message(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a trade message from TradingView."""
        try:
            self.logger.info(f"Processing trade: {trade_data}")
            
            # Extract trade details
            request_data = trade_data.get('request_data', {})
            
            # Basic validation
            if not self._validate_trade_request(request_data):
                return {"error": "Invalid trade request"}
            
            # Execute trade
            result = self.executor.execute_market_order(request_data)
            
            # Log result
            if 'error' in result:
                self.logger.error(f"Trade execution failed: {result['error']}")
                return result
                
            self.logger.info(f"Trade executed successfully: {result}")
            
            # Store result in queue for tracking
            self.queue.complete_trade(trade_data.get('id', 'unknown'), result)
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing trade: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
    
    def _validate_trade_request(self, request: Dict[str, Any]) -> bool:
        """Validate trade request data."""
        required_fields = ['instrument', 'side', 'qty', 'type']
        
        # Check required fields
        if not all(field in request for field in required_fields):
            self.logger.error(f"Missing required fields. Got: {request.keys()}")
            return False
        
        # Validate quantity
        try:
            qty = float(request['qty'])
            if qty <= 0:
                self.logger.error(f"Invalid quantity: {qty}")
                return False
        except ValueError:
            self.logger.error(f"Invalid quantity format: {request['qty']}")
            return False
        
        # Validate side
        if request['side'].lower() not in ['buy', 'sell']:
            self.logger.error(f"Invalid side: {request['side']}")
            return False
        
        # Validate type (for now, only support market orders)
        if request['type'].lower() != 'market':
            self.logger.error(f"Unsupported order type: {request['type']}")
            return False
            
        return True