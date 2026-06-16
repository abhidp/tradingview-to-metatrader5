# app/api/mt5_api.py
"""MT5 terminal discovery + native Browse endpoints (shared by wizard & Settings)."""
from typing import Callable, Optional

from fastapi import FastAPI

from src.services.mt5_service import discover_mt5_terminals
from app.storage.settings_store import SettingsStore


def _current_terminal() -> Optional[str]:
    return SettingsStore().get("mt5.terminal_path")


def add_mt5_routes(app: FastAPI, pick_file: Optional[Callable[[], Optional[str]]] = None) -> None:
    @app.get("/api/mt5/terminals")
    def list_terminals():
        return {"terminals": discover_mt5_terminals(), "current": _current_terminal()}

    @app.post("/api/mt5/browse-terminal")
    def browse_terminal():
        # pick_file runs the native dialog on the GUI thread; absent in headless/tests.
        path = pick_file() if pick_file is not None else None
        return {"path": path}
