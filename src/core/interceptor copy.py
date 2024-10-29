from mitmproxy import ctx, http
import logging
import json

# Disable mitmproxy's default logging
ctx.log.silent = True
ctx.options.flow_detail = 0

class TradingViewInterceptor:
    def __init__(self):
        self.base_path = "icmarkets.tv.ctrader.com/accounts/40807470"
        print("\n🚀 Trade interceptor initialized")
        print("Watching for trades...\n")

    def should_log_request(self, flow: http.HTTPFlow) -> bool:
        """Strictly check if we should log this request."""
        url = flow.request.pretty_url
        
        # Must be our base path
        if self.base_path not in url:
            return False
            
        # Must be one of our two target endpoints
        if '/orders?locale=' in url and 'requestId=' in url:
            return True
        if '/executions?locale=' in url and 'instrument=' in url:
            return True
            
        return False

    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        if not self.should_log_request(flow):
            return
            
        print(f"\n{'='*50}")
        print(f"📡 Intercepted Request: {flow.request.pretty_url}")
        
        if flow.request.method == "POST":
            if flow.request.urlencoded_form:
                print("\n📤 Trade Data:")
                print(json.dumps(dict(flow.request.urlencoded_form), indent=2))

    def response(self, flow: http.HTTPFlow) -> None:
        """Handle responses."""
        if not self.should_log_request(flow):
            return
            
        if flow.response and flow.response.content:
            try:
                response_data = json.loads(flow.response.content.decode('utf-8'))
                print("\n📥 Response Data:")
                print(json.dumps(response_data, indent=2))
                print(f"{'='*50}\n")
            except:
                pass

addons = [TradingViewInterceptor()]