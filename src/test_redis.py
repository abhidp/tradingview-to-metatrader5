import redis
import sys

print(f"Python version: {sys.version}")
print(f"Redis version: {redis.__version__}")

try:
    # Try to connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print("✓ Successfully connected to Redis server")
except Exception as e:
    print(f"✗ Failed to connect to Redis: {e}")