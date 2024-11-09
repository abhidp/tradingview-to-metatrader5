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
        
        # Control flag for graceful shutdown
        self._stop = False
        self._pubsub = None
        
        # Initialize Redis silently (will send status after subscription)
        self._init_redis(send_status=False)
    
    def _init_redis(self, send_status=True) -> None:
        """Initialize Redis and clean up any stale data."""
        try:
            # Clear any old data
            self.redis.delete(
                'trades:pending',
                'trades:processing',
                'trades:completed',
                'trades:failed'
            )
            
            # Publish system startup message only if requested
            if send_status:
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
            self._pubsub = self.redis.pubsub()
            
            # Subscribe to all channels with message handlers
            channel_handlers = {
                self.channels['trades']: self._handle_message(callback, 'trade'),
                self.channels['status']: self._handle_message(callback, 'status'),
                self.channels['errors']: self._handle_message(callback, 'error')
            }
            
            self._pubsub.subscribe(**channel_handlers)
            self.logger.info("Subscribed to trade channels")
            
            # Now that we're subscribed, send the initialization status
            self._init_redis(send_status=True)
            
            # Start listening loop with timeout
            while not self._stop:
                message = self._pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        msg_type = self._get_message_type(message['channel'])
                        callback(msg_type, data)
                    except json.JSONDecodeError:
                        self.logger.error("Invalid JSON message received")
                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")
                        
        except Exception as e:
            if not self._stop:  # Only log if not stopping intentionally
                self.logger.error(f"Error in subscription loop: {e}")
        finally:
            self._cleanup_subscription()
    
    def _get_message_type(self, channel: bytes) -> str:
        """Get message type from channel name."""
        channel_str = channel.decode('utf-8')
        for msg_type, chan in self.channels.items():
            if chan == channel_str:
                return msg_type
        return 'unknown'
    
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
    
    def _cleanup_subscription(self):
        """Clean up Redis subscription."""
        try:
            if self._pubsub:
                self._pubsub.unsubscribe()
                self._pubsub.close()
                self._pubsub = None
        except Exception as e:
            self.logger.error(f"Error cleaning up subscription: {e}")
    
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
        
    def close(self):
        """Close the Redis connection."""
        try:
            # Signal subscription loop to stop
            self._stop = True
            
            # Send shutdown message before closing
            self.publish_status("Queue system shutting down")
            
            # Clean up subscription
            self._cleanup_subscription()
            
            # Close Redis connection
            if hasattr(self, 'redis'):
                self.redis.close()
                
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")