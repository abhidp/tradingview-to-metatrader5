import json
from typing import Optional, Dict, Any
from src.models.trade import Trade
from src.utils.file_handler import TradeFileHandler
from src.config.constants import TRADE_FIELDS, SEPARATOR_LINE
from src.utils.logging import original_print

class TradeHandler:
    """Handles trade processing and logging."""
    
    def __init__(self):
        self.file_handler = TradeFileHandler()
    
    def extract_response_data(self, flow) -> Optional[Dict[str, Any]]:
        """Extract response data from flow."""
        if flow.response and flow.response.content:
            try:
                return json.loads(flow.response.content.decode('utf-8'))
            except:
                return {"error": "Unable to parse response"}
        return None
    
    def process_trade(self, flow) -> None:
        """Process and log a trade."""
        response_data = self.extract_response_data(flow)
        trade = Trade.from_flow(flow, response_data)
        
        if trade.is_valid():
            self.log_trade(trade)
    
    def log_trade(self, trade: Trade) -> None:
        """Log trade to file and console."""
        # Save to file
        self.file_handler.write_trade(trade.to_dict())
        
        # Print to console
        request_data = trade.request_data
        original_print("\n📊 Trade Executed:")
        for field, label in TRADE_FIELDS.items():
            original_print(f"{label}: {request_data.get(field, 'N/A')}")
        original_print(SEPARATOR_LINE)
    
    def cleanup(self) -> None:
        """Cleanup operations."""
        self.file_handler.close_file()