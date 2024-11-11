While async operations can improve concurrent processing, they may not necessarily decrease the actual execution time of individual operations, especially when:

1. The main bottlenecks are:
   - Network latency between TradingView and your system
   - MT5 API response time
   - Physical trade execution time on the broker's side

Here are some actual optimization options that might help speed up execution:

1. Network Optimization:
```python
# In MT5Service
# Add timeouts and optimize network settings
self.mt5_config = {
    'timeout': 5000,  # milliseconds
    'retry_count': 3,
    'retry_delay': 0.1  # seconds
}
```

2. Pre-cache Symbol Information:
```python
class MT5Service:
    def __init__(self):
        self.symbol_cache = {}
        
    def cache_symbols(self):
        """Cache symbol information for faster access."""
        for symbol in self.symbol_map.values():
            if mt5.symbol_select(symbol, True):
                self.symbol_cache[symbol] = mt5.symbol_info(symbol)._asdict()
```

3. Direct Connection Mode:
```python
# In docker-compose.yml
services:
  db:
    network_mode: "host"  # For better database performance
```

4. Optimize MT5 Connection:
```python
# In MT5Service
def initialize(self):
    try:
        mt5.initialize(
            path="path_to_terminal64.exe",
            login=self.account,
            password=self.password,
            server=self.server,
            timeout=5000,
            portable=True  # Faster startup
        )
```

5. Use Binary Protocol for Redis:
```python
# In queue_handler.py
def __init__(self):
    self.redis = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        protocol=3,  # Use RESP3 protocol
        socket_keepalive=True,
        socket_timeout=1
    )
```

6. Profile and Monitor:
```python
# Add this utility to track exactly where time is spent
class Timer:
    def __init__(self):
        self.checkpoints = {}
        self.start_time = time.time()
    
    def checkpoint(self, name: str):
        self.checkpoints[name] = time.time() - self.start_time
```

Usage:
```python
async def process_trade(self, trade_data: Dict[str, Any]) -> None:
    timer = Timer()
    
    # Check network latency
    timer.checkpoint("start")
    
    # Execute trade
    result = await self.mt5.execute_market_order(trade_data)
    timer.checkpoint("mt5_execution")
    
    # Update database
    await self.db.update_trade_status(trade_id, status, update_data)
    timer.checkpoint("db_update")
    
    print("Execution breakdown:")
    for point, time_taken in timer.checkpoints.items():
        print(f"{point}: {time_taken*1000:.2f}ms")
```

They might provide more tangible speed improvements than the async changes we made.

Remember to measure and profile before and after each optimization to ensure it's actually helping in your specific case.