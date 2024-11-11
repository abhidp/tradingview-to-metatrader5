import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

logger = logging.getLogger(__name__)

def get_env_var(key: str) -> str:
    """Get environment variable with proper error handling."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

# Database configuration with required environment variables
DB_CONFIG = {
    'host': get_env_var('DB_HOST'),
    'port': get_env_var('DB_PORT'),
    'database': get_env_var('DB_NAME'),
    'user': get_env_var('DB_USER'),
    'password': get_env_var('DB_PASSWORD')
}

# Construct database URL with retry parameters
DATABASE_URL = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    "?connect_timeout=10"  # Add connection timeout
)

# Log connection details (excluding sensitive info)
logger.info("Database Connection Details:")
logger.info(f"Host: {DB_CONFIG['host']}")
logger.info(f"Port: {DB_CONFIG['port']}")
logger.info(f"Database: {DB_CONFIG['database']}")
logger.info(f"User: {DB_CONFIG['user']}")