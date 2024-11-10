import redis
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Callable

logger = logging.getLogger('RedisQueue')

class RedisQueue:
    """Handles Redis queue operations with Pub/Sub support."""
    
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
    
    def subscribe(self, callback: Callable[[str, Dict], None]) -> None:
        """Subscribe to trade channel with callback."""
        try:
            # Create new connection for subscription
            pubsub = self.redis.pubsub()
            
            # Subscribe to all channels
            pubsub.subscribe(**{
                self.channels['trades']: self._handle_message(callback, 'trade'),
                self.channels['status']: self._handle_message(callback, 'status'),
                self.channels['errors']: self._handle_message(callback, 'error')
            })
            
            # Start listening
            self.logger.info("Subscribed to trade channels")
            pubsub.run_in_thread(sleep_time=0.001)
            
        except Exception as e:
            self.logger.error(f"Error subscribing: {e}")
            raise
    
    def _handle_message(self, callback: Callable, msg_type: str) -> Callable:
        """Create message handler for type."""
        def handler(message):
            try:
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    callback(msg_type, data)
            except Exception as e:
                self.logger.error(f"Error handling {msg_type} message: {e}")
        return handler
    
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