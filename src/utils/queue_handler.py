import redis
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Callable, Awaitable, Union
from functools import partial

logger = logging.getLogger('RedisQueue')

class RedisQueue:
    def __init__(self, host='localhost', port=6379, db=0):
        self.logger = logging.getLogger('RedisQueue')
        
        # Main Redis connection for operations
        self.redis = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            decode_responses=True,
            socket_timeout=5
        )

        # Channel names for pub/sub
        self.channels = {
            'trades': 'trades:channel',      # Main trade execution channel
            'status': 'trades:status',       # Status updates channel
            'errors': 'trades:errors'        # Error notifications channel
        }

        # Initialize event loop for async operations
        self.loop = asyncio.get_event_loop()
        self.pubsub = None
        self.pubsub_thread = None
        
        # Initialize Redis
        self._init_redis()
    
    def _init_redis(self) -> None:
        """Initialize Redis and clean up any stale data."""
        try:
            # Clear any old data
            self.redis.delete(
                'trades:pending',
                'trades:processing',
                'trades:completed',
                'trades:failed'
            )
            
            # Publish system startup message
            self.publish_status("Queue system initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing Redis: {e}")
    
    def publish_status(self, message: str) -> None:
        """Publish status update."""
        try:
            self.redis.publish(self.channels['status'], 
                             json.dumps({
                                 'type': 'status',
                                 'message': message,
                                 'timestamp': datetime.now().isoformat()
                             }))
        except Exception as e:
            self.logger.error(f"Error publishing status: {e}")
    
    async def async_publish_status(self, message: str) -> None:
        """Publish status update asynchronously."""
        try:
            await self.loop.run_in_executor(
                None,
                self.publish_status,
                message
            )
        except Exception as e:
            self.logger.error(f"Error publishing async status: {e}")
    
    def push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Publish trade data to channel."""
        try:
            # Generate trade ID
            trade_id = f"trade_{datetime.now().timestamp()}"
            
            # Prepare message
            message = {
                'id': trade_id,
                'data': trade_data,
                'timestamp': datetime.now().isoformat()
            }
            
            # Publish to trades channel
            self.redis.publish(
                self.channels['trades'],
                json.dumps(message)
            )
            
            self.logger.info(f"Trade {trade_id} published to channel")
            return trade_id
            
        except Exception as e:
            self.logger.error(f"Error publishing trade: {e}")
            # Publish error
            self.redis.publish(
                self.channels['errors'],
                json.dumps({
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            )
            raise
    
    async def async_push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Publish trade data to channel asynchronously."""
        try:
            return await self.loop.run_in_executor(
                None,
                self.push_trade,
                trade_data
            )
        except Exception as e:
            self.logger.error(f"Error publishing async trade: {e}")
            raise

    def _handle_message(self, callback: Union[Callable, Awaitable], msg_type: str) -> Callable:
        """Create message handler that supports both sync and async callbacks."""
        def handler(message):
            try:
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    if asyncio.iscoroutinefunction(callback):
                        # Handle async callback
                        future = asyncio.run_coroutine_threadsafe(
                            callback(msg_type, data),
                            self.loop
                        )
                        # Handle any exceptions from the future
                        try:
                            future.result(timeout=10)  # 10 second timeout
                        except Exception as e:
                            self.logger.error(f"Async callback error: {e}")
                    else:
                        # Handle sync callback
                        callback(msg_type, data)
            except Exception as e:
                self.logger.error(f"Error handling {msg_type} message: {e}")
        return handler
    
    def subscribe(self, callback: Callable[[str, Dict], None]) -> None:
        """Subscribe to trade channel with callback."""
        try:
            # Create new connection for subscription
            self.pubsub = self.redis.pubsub()
            
            # Subscribe to all channels
            self.pubsub.subscribe(**{
                self.channels['trades']: self._handle_message(callback, 'trade'),
                self.channels['status']: self._handle_message(callback, 'status'),
                self.channels['errors']: self._handle_message(callback, 'error')
            })
            
            # Start listening
            # self.logger.info("Subscribed to trade channels")
            self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.001)
            
        except Exception as e:
            self.logger.error(f"Error subscribing: {e}")
            raise
    
    async def async_subscribe(self, callback: Union[Callable, Awaitable]) -> None:
        """Subscribe to trade channels asynchronously."""
        try:
            await self.loop.run_in_executor(
                None,
                self.subscribe,
                callback
            )
        except Exception as e:
            self.logger.error(f"Error in async subscribe: {e}")
            raise
    
    def get_queue_status(self) -> Dict[str, int]:
        """Get current queue status."""
        try:
            return {
                'trades_channel': self.redis.pubsub_numsub(self.channels['trades'])[0][1],
                'status_channel': self.redis.pubsub_numsub(self.channels['status'])[0][1],
                'errors_channel': self.redis.pubsub_numsub(self.channels['errors'])[0][1]
            }
        except Exception as e:
            self.logger.error(f"Error getting queue status: {e}")
            return {'error': str(e)}

    async def async_get_queue_status(self) -> Dict[str, int]:
        """Get current queue status asynchronously."""
        try:
            return await self.loop.run_in_executor(
                None,
                self.get_queue_status
            )
        except Exception as e:
            self.logger.error(f"Error getting async queue status: {e}")
            return {'error': str(e)}
    
    def cleanup(self) -> None:
        """Cleanup Redis connections with proper thread shutdown."""
        try:
            # Stop pubsub thread if running
            if self.pubsub_thread is not None:
                self.logger.info("Stopping pubsub thread...")
                self.pubsub_thread.stop()
                self.pubsub_thread.join(timeout=1.0)  # Wait for thread to finish
                self.pubsub_thread = None
            
            # Unsubscribe and close pubsub connection
            if self.pubsub is not None:
                self.logger.info("Closing pubsub connection...")
                self.pubsub.unsubscribe()
                self.pubsub.close()
                self.pubsub = None
            
            # Close main Redis connection
            if self.redis is not None:
                self.logger.info("Closing main Redis connection...")
                self.redis.close()
                self.redis = None
            
            self.logger.info("Redis connections cleaned up")
        except Exception as e:
            self.logger.error(f"Error during Redis cleanup: {e}")