import redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('QueueReset')

def reset_queues():
    """Reset all Redis queues."""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Clear all trade-related keys
        keys = ['trades:pending', 'trades:processing', 'trades:completed', 'trades:failed']
        for key in keys:
            r.delete(key)
            logger.info(f"Cleared queue: {key}")
        
        logger.info("All queues reset successfully")
        
    except Exception as e:
        logger.error(f"Error resetting queues: {e}")

if __name__ == "__main__":
    reset_queues()