"""FastAPI app: JSON API + static UI for the desktop shell."""
import logging
from typing import Callable, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.engine_controller import EngineController, ProxyPortInUseError
from app.api.config_api import (SettingsValidationError, get_settings,
                                get_symbols, update_settings, update_symbols)
from app.api.logs import read_log_tail
from app.api.trades import query_trades
from app.api.wizard import add_wizard_routes
from app.api.mt5_api import add_mt5_routes
from app.api.profiles_api import add_profile_routes
from app.paths import get_data_dir
from app.resources import resource_path

logger = logging.getLogger("ApiServer")

UI_DIR = resource_path("app/ui")


def create_app(controller: EngineController, focus_callback: Optional[Callable] = None,
               pick_file: Optional[Callable] = None) -> FastAPI:
    app = FastAPI(title="TV2MT5 Desktop")
    log_file = get_data_dir() / "logs" / "tv2mt5.log"

    @app.get("/api/status")
    def get_status():
        return controller.status().to_dict()

    @app.post("/api/engine/start")
    async def start_engine():
        try:
            status = await controller.start()
        except ProxyPortInUseError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return status.to_dict()

    @app.post("/api/engine/stop")
    async def stop_engine():
        return (await controller.stop()).to_dict()

    @app.post("/api/engine/restart")
    async def restart_engine():
        try:
            status = await controller.restart()
        except ProxyPortInUseError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return status.to_dict()

    @app.get("/api/settings")
    def read_settings():
        return get_settings()

    @app.put("/api/settings")
    def write_settings(payload: dict = Body(...)):
        try:
            update_settings(payload)
        except SettingsValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"ok": True}

    @app.get("/api/symbols")
    def read_symbols():
        return get_symbols()

    @app.put("/api/symbols")
    def write_symbols(payload: dict = Body(...)):
        try:
            update_symbols(payload)
        except SettingsValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"ok": True}

    @app.get("/api/logs")
    def get_logs(after: int = Query(0, ge=0)):
        lines, cursor = read_log_tail(log_file, after=after)
        return {"lines": lines, "cursor": cursor}

    @app.get("/api/trades")
    def get_trades(
        limit: int = Query(10, ge=1, le=200),
        offset: int = Query(0, ge=0),
        status: str = Query(None),
    ):
        rows, total = query_trades(limit=limit, offset=offset, status=status)
        return {"trades": rows, "total": total}

    @app.post("/api/focus")
    def focus():
        if focus_callback is not None:
            focus_callback()
        return {"ok": True}

    add_wizard_routes(app)
    add_mt5_routes(app, pick_file=pick_file)
    add_profile_routes(app, controller)

    @app.get("/")
    def index():
        p = UI_DIR / "index.html"
        if not p.exists():
            raise HTTPException(status_code=404, detail="UI not available")
        return FileResponse(p)

    if UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    return app
