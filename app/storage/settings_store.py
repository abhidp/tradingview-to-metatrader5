"""SQLite-backed settings store (replaces the .env workflow).

Backed by the shared engine from src/config/database.py (Plan 1). Values are
stored as text; typed accessors interpret them. Secret-flagged keys are written
through a SecretBox (plaintext by default).
"""
import json
import logging
from typing import Optional

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
        finally:
            session.close()

    # --- typed accessors ---

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        raw = self.get(key)
        return default if raw is None else int(raw)

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
