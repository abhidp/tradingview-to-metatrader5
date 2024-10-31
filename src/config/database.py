import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

def get_env_var(key: str, default: str = None) -> str:
    """Get environment variable with error handling."""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

# Database configuration
DB_CONFIG = {
    'host': get_env_var('DB_HOST', 'localhost'),
    'port': get_env_var('DB_PORT', '5432'),
    'database': get_env_var('DB_NAME', 'tradingview'),
    'user': get_env_var('DB_USER', 'tvuser'),
    'password': get_env_var('DB_PASSWORD', 'tvpassword')
}

# Construct database URL
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"