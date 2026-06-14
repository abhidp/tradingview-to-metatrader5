"""FastAPI app: JSON API + static UI for the desktop shell."""
import logging
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.engine_controller import EngineController, ProxyPortInUseError
from app.api.logs import read_log_tail
from app.api.trades import recent_trades
from app.paths import get_data_dir

logger = logging.getLogger("ApiServer")

UI_DIR = Path(__file__).parent.parent / "ui"


def _log_path() -> Path:
    return get_data_dir() / "logs" / "tv2mt5.log"


def create_app(controller: EngineController, focus_callback: Optional[Callable] = None) -> FastAPI:
    app = FastAPI(title="TV2MT5 Desktop")

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

    @app.get("/api/logs")
    def get_logs(after: int = Query(0, ge=0)):
        lines, cursor = read_log_tail(_log_path(), after=after)
        return {"lines": lines, "cursor": cursor}

    @app.get("/api/trades")
    def get_trades(limit: int = Query(10, ge=1, le=200)):
        return {"trades": recent_trades(limit=limit)}

    @app.post("/api/focus")
    def focus():
        if focus_callback is not None:
            focus_callback()
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(UI_DIR / "index.html")

    if UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    return app
