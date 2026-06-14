"""SQLite-backed settings store (replaces the .env workflow).

Backed by the shared engine from src/config/database.py (Plan 1). Values are
stored as text; typed accessors interpret them. Secret-flagged keys are written
through a SecretBox (plaintext by default).
"""
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv

from sqlalchemy import Column, String, Text
from sqlalchemy.orm import declarative_base

from src.config.database import get_engine, get_session_factory
from app.storage.secret_box import PlaintextSecretBox, SecretBox

logger = logging.getLogger("SettingsStore")

SettingsBase = declarative_base()

# Keys whose values must go through the SecretBox.
SECRET_KEYS = {"mt5.password"}


class Settings(SettingsBase):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text)


# Maps a .env variable -> (settings key, is_secret).
_ENV_MAP = {
    "TV_BROKER_URL": ("tv.broker_url", False),
    "TV_ACCOUNT_ID": ("tv.account_id", False),
    "MT5_ACCOUNT": ("mt5.account", False),
    "MT5_PASSWORD": ("mt5.password", True),
    "MT5_SERVER": ("mt5.server", False),
    "MT5_TERMINAL_PATH": ("mt5.terminal_path", False),
    "MT5_DEFAULT_SUFFIX": ("symbols.default_suffix", False),
    "MT5_SYMBOL_MAP": ("symbols.map", False),
}


class SettingsStore:
    def __init__(self, secret_box: Optional[SecretBox] = None) -> None:
        self.secret_box = secret_box if secret_box is not None else PlaintextSecretBox()
        # Ensure the settings table exists on the shared engine.
        SettingsBase.metadata.create_all(bind=get_engine())
        self._Session = get_session_factory()

    # --- core string get/set ---

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        session = self._Session()
        try:
            row = session.get(Settings, key)
            return row.value if row is not None else default
        finally:
            session.close()

    def set(self, key: str, value) -> None:
        session = self._Session()
        try:
            row = session.get(Settings, key)
            if row is None:
                session.add(Settings(key=key, value=str(value)))
            else:
                row.value = str(value)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- typed accessors ---

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except (ValueError, TypeError):
            logger.warning("Non-integer value for %s; using default", key)
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def get_json(self, key: str, default=None):
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Malformed JSON for %s; using default", key)
            return default

    # --- secrets ---

    def get_secret(self, key: str) -> Optional[str]:
        raw = self.get(key)
        return None if raw is None else self.secret_box.unprotect(raw)

    def set_secret(self, key: str, value: str) -> None:
        self.set(key, self.secret_box.protect(value))

    # --- bulk ---

    def all(self, *, redact_secrets: bool = True) -> dict:
        session = self._Session()
        try:
            rows = session.query(Settings).all()
            out = {}
            for row in rows:
                if redact_secrets and row.key in SECRET_KEYS:
                    out[row.key] = "***"
                else:
                    out[row.key] = row.value
            return out
        finally:
            session.close()

    def seed_from_env_once(self) -> bool:
        """Import .env values into the store on first run only.

        Returns True if it seeded this call, False if already seeded. After
        seeding, the store is authoritative and .env is neither read nor needed.
        """
        if self.get_bool("meta.seeded"):
            return False
        load_dotenv()
        for env_var, (key, is_secret) in _ENV_MAP.items():
            value = os.getenv(env_var)
            if value is None or value == "":
                continue
            if is_secret:
                self.set_secret(key, value)
            else:
                self.set(key, value)
        self.set("meta.seeded", "1")
        logger.info("Seeded settings from .env (first run)")
        return True
