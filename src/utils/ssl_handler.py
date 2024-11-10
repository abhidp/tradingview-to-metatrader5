# src/utils/ssl_handler.py
import warnings
import urllib3
import contextlib
from functools import wraps

def silence_ssl_warnings():
    """Silence SSL verification warnings."""
    # Disable SSL verification warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
@contextlib.contextmanager
def handled_ssl_context():
    """Context manager to handle SSL warnings within a specific context."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)
        yield

def handle_ssl_warnings(func):
    """Decorator to handle SSL warnings for specific functions."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with handled_ssl_context():
            return func(*args, **kwargs)
    return wrapper