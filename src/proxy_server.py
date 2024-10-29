import sys
import threading
import logging
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import ssl
import json
from datetime import datetime
from pathlib import Path
import http.client

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.trade_handler import TradeHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ProxyServer')

class TradingViewProxyHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.trade_handler = TradeHandler()
        super().__init__(*args, **kwargs)

    def do_CONNECT(self):
        """Handle HTTPS CONNECT requests."""
        try:
            # Parse the host and port from the request
            host, port = self.path.split(':')
            port = int(port)

            # Connect to the remote server
            dest = socket.create_connection((host, port))

            # Send 200 Connection established
            self.send_response(200)
            self.end_headers()

            # Start tunneling
            self._tunnel(self.connection, dest)
        except Exception as e:
            logger.error(f"CONNECT error: {e}")
            self.send_error(500)

    def _tunnel(self, client, server):
        """Create a tunnel between client and server."""
        try:
            client.setblocking(0)
            server.setblocking(0)
            while True:
                # Try to read from both connections
                try:
                    data = client.recv(4096)
                    if data:
                        server.sendall(data)
                except socket.error:
                    pass

                try:
                    data = server.recv(4096)
                    if data:
                        client.sendall(data)
                except socket.error:
                    pass
        except Exception as e:
            logger.error(f"Tunnel error: {e}")
        finally:
            client.close()
            server.close()

    def do_GET(self):
        """Handle GET requests."""
        try:
            # Forward the request to the destination server
            parsed_url = urlparse(self.path)
            conn = http.client.HTTPSConnection(parsed_url.netloc)
            conn.request("GET", parsed_url.path + "?" + parsed_url.query if parsed_url.query else parsed_url.path)
            response = conn.getresponse()
            
            # Send response back to client
            self.send_response(response.status)
            for header, value in response.getheaders():
                self.send_header(header, value)
            self.end_headers()
            self.wfile.write(response.read())
            
        except Exception as e:
            logger.error(f"GET error: {e}")
            self.send_error(500)

    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed_url = urlparse(self.path)
            
            # Check if this is a trade execution
            if 'orders' in parsed_url.path:
                # Get request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Parse form data
                trade_data = parse_qs(post_data.decode('utf-8'))
                logger.info(f"Intercepted trade: {trade_data}")
                
                # Process trade
                self.trade_handler.process_trade_request(trade_data)
            
            # Forward the request to the destination server
            conn = http.client.HTTPSConnection(parsed_url.netloc)
            headers = dict(self.headers)
            conn.request("POST", parsed_url.path, post_data, headers)
            response = conn.getresponse()
            
            # Send response back to client
            self.send_response(response.status)
            for header, value in response.getheaders():
                self.send_header(header, value)
            self.end_headers()
            self.wfile.write(response.read())
            
        except Exception as e:
            logger.error(f"POST error: {e}")
            self.send_error(500)

    def do_OPTIONS(self):
        """Handle OPTIONS requests."""
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()
        except Exception as e:
            logger.error(f"OPTIONS error: {e}")
            self.send_error(500)

    def log_message(self, format, *args):
        """Override to control logging output."""
        if isinstance(args[0], str) and "orders" in args[0]:
            logger.info(format % args)
        elif not isinstance(args[0], str):
            logger.debug(format % args)

class ProxyServer:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.server = None
        self.running = False
    
    def start(self):
        """Start the proxy server."""
        try:
            self.server = HTTPServer((self.host, self.port), TradingViewProxyHandler)
            self.running = True
            
            logger.info(f"Starting proxy server on {self.host}:{self.port}")
            print(f"\nProxy server running on http://{self.host}:{self.port}")
            print("Press Ctrl+C to stop")
            
            # Run server in the main thread
            self.server.serve_forever()
            
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            self.stop()
    
    def stop(self):
        """Stop the proxy server."""
        if self.server:
            self.running = False
            self.server.shutdown()
            self.server.server_close()
            logger.info("Proxy server stopped")

def main():
    try:
        server = ProxyServer()
        server.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        print("\nProxy server stopped.")

if __name__ == "__main__":
    main()