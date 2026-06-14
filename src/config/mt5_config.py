"""MT5 connection config, now sourced from the settings store (was .env).

Kept as a thin module so existing imports (`from src.config.mt5_config import
get_mt5_config`) keep working. The import-time MT5_CONFIG dict was removed: it
read os.getenv at import and raised on a fresh install where config lives only
in the SQLite settings table.
"""
from app.config_accessors import get_mt5_config

__all__ = ["get_mt5_config"]
