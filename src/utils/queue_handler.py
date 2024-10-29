import redis
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

class RedisQueue:
    """Handles Redis queue operations."""
    
    def __init__(self, host='localhost', port=6379, db=0):
        self.logger = logging.getLogger('RedisQueue')
        self.redis = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            decode_responses=True,
            socket_timeout=5
        )
        # Queue keys
        self.pending_key = 'trades:pending'
        self.processing_key = 'trades:processing'
        self.completed_key = 'trades:completed'
        self.failed_key = 'trades:failed'
        
        # Initialize queues if needed
        self._init_queues()
    
    def _init_queues(self):
        """Initialize Redis queues if they don't exist."""
        try:
            # Clear any existing incorrect data structures
            for key in [self.pending_key, self.processing_key, self.completed_key, self.failed_key]:
                if self.redis.exists(key) and not self.redis.type(key) == b'list':
                    self.redis.delete(key)
            
            # Initialize empty lists if they don't exist
            pipeline = self.redis.pipeline()
            for key in [self.pending_key, self.processing_key, self.completed_key, self.failed_key]:
                pipeline.lpush(key, '') if not self.redis.exists(key) else None
                pipeline.lrem(key, 0, '')  # Remove empty string placeholder
            pipeline.execute()
            
        except Exception as e:
            self.logger.error(f"Error initializing queues: {e}")
    
    def push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Push trade to queue."""
        try:
            trade_id = f"trade_{datetime.now().timestamp()}"
            trade_item = json.dumps({
                'id': trade_id,
                'data': trade_data,
                'timestamp': datetime.now().isoformat()
            })
            self.redis.lpush(self.pending_key, trade_item)
            self.logger.info(f"Trade {trade_id} pushed to queue")
            return trade_id
        except Exception as e:
            self.logger.error(f"Error pushing trade to queue: {e}")
            raise
    
    def get_trade(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Get next trade from queue."""
        try:
            # Move from pending to processing
            trade_item = self.redis.rpoplpush(self.pending_key, self.processing_key)
            if not trade_item:
                return None
            
            trade = json.loads(trade_item)
            return trade['id'], trade['data']
            
        except Exception as e:
            self.logger.error(f"Error getting trade from queue: {e}")
            return None
    
    def complete_trade(self, trade_id: str, result: Dict[str, Any]) -> None:
        """Mark trade as complete."""
        try:
            # Find trade in processing queue
            trade_item = self._find_and_remove_from_list(self.processing_key, trade_id)
            if trade_item:
                trade = json.loads(trade_item)
                trade['result'] = result
                trade['completed_at'] = datetime.now().isoformat()
                self.redis.lpush(self.completed_key, json.dumps(trade))
                self.logger.info(f"Trade {trade_id} marked as complete")
                
        except Exception as e:
            self.logger.error(f"Error completing trade {trade_id}: {e}")
    
    def fail_trade(self, trade_id: str, error: str) -> None:
        """Mark trade as failed."""
        try:
            # Find trade in processing queue
            trade_item = self._find_and_remove_from_list(self.processing_key, trade_id)
            if trade_item:
                trade = json.loads(trade_item)
                trade['error'] = error
                trade['failed_at'] = datetime.now().isoformat()
                self.redis.lpush(self.failed_key, json.dumps(trade))
                self.logger.info(f"Trade {trade_id} marked as failed: {error}")
                
        except Exception as e:
            self.logger.error(f"Error failing trade {trade_id}: {e}")
    
    def _find_and_remove_from_list(self, key: str, trade_id: str) -> Optional[str]:
        """Find and remove a trade from a list by ID."""
        list_length = self.redis.llen(key)
        for i in range(list_length):
            item = self.redis.lindex(key, i)
            if not item:
                continue
            
            trade = json.loads(item)
            if trade['id'] == trade_id:
                # Remove this item
                self.redis.lrem(key, 1, item)
                return item
        return None
    
    def get_queue_status(self) -> Dict[str, int]:
        """Get current queue status."""
        try:
            return {
                'pending': self.redis.llen(self.pending_key),
                'processing': self.redis.llen(self.processing_key),
                'completed': self.redis.llen(self.completed_key),
                'failed': self.redis.llen(self.failed_key)
            }
        except Exception as e:
            self.logger.error(f"Error getting queue status: {e}")
            return {'error': str(e)}