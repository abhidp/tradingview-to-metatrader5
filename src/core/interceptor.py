from mitmproxy import ctx, http
from src.config.constants import BASE_URL, STARTUP_MESSAGE, MONITORING_MESSAGE
from src.utils.logging import original_print
from src.core.trade_handler import TradeHandler

class TradingViewInterceptor:
    """Main interceptor class for handling trading view requests."""
    
    def __init__(self):
        self.trade_handler = TradeHandler()
        self._print_startup_message()
    
    def _print_startup_message(self):
        """Print startup message to console."""
        original_print(STARTUP_MESSAGE)
        original_print(MONITORING_MESSAGE)
    
    def is_trade_execution(self, flow: http.HTTPFlow) -> bool:
        """Check if the request is a trade execution."""
        return (BASE_URL in flow.request.pretty_url and 
                flow.request.method == "POST" and
                flow.request.urlencoded_form)
    
    def response(self, flow: http.HTTPFlow) -> None:
        """Handle responses."""
        if self.is_trade_execution(flow):
            self.trade_handler.process_trade(flow)
    
    def done(self):
        """Cleanup when proxy is shutdown."""
        self.trade_handler.cleanup()