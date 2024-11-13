import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

def get_required_env(key: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

MT5_CONFIG = {
    'account': int(get_required_env('MT5_ACCOUNT')),
    'password': get_required_env('MT5_PASSWORD'),
    'server': get_required_env('MT5_SERVER'),
}