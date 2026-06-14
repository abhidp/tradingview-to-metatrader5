"""Desktop entrypoint: window (main thread) + API/engine loop (thread) + tray (thread).

Process model (Plan 3a):
- main thread runs the pywebview window (WebView2)
- a background thread runs one asyncio loop hosting uvicorn (FastAPI) + the engine
- a tray thread runs the pystray icon
Single-instance guard: bind the control port; if taken, focus the running app and exit.
"""
import logging
import threading

import uvicorn
import webview

from app.engine_controller import EngineController
from app.api.server import create_app
from app.logging_setup import setup_logging
from app.singleton import (CONTROL_HOST, CONTROL_PORT, acquire_single_instance,
                           focus_running_instance, is_another_instance_running)
from app.tray import build_tray

logger = logging.getLogger("Desktop")

_window = None


def _run_api(controller: EngineController) -> None:
    """Run uvicorn (FastAPI + engine loop) on this thread's own asyncio loop."""
    app = create_app(controller, focus_callback=_focus_window)
    config = uvicorn.Config(app, host=CONTROL_HOST, port=CONTROL_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.run()  # creates and runs its own asyncio loop on this thread


def _focus_window() -> None:
    if _window is not None:
        try:
            _window.show()
            _window.restore()
        except Exception as e:  # noqa: BLE001
            logger.info("focus window failed: %s", e)


def main() -> None:
    global _window
    setup_logging()

    if is_another_instance_running():
        focus_running_instance()
        print("TV2MT5 is already running.")
        return
    lock = acquire_single_instance()
    if lock is None:
        focus_running_instance()
        print("TV2MT5 is already running.")
        return
    # Release the probe socket so uvicorn can bind the port; the window of overlap
    # is tiny and the is_another_instance_running check above already gated us.
    lock.close()

    controller = EngineController()

    api_thread = threading.Thread(target=_run_api, args=(controller,), daemon=True)
    api_thread.start()

    def on_quit(icon):
        try:
            icon.stop()
        finally:
            if _window is not None:
                _window.destroy()

    tray = build_tray(on_open=_focus_window, on_quit=on_quit)
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    _window = webview.create_window(
        "TV2MT5 Desktop",
        f"http://{CONTROL_HOST}:{CONTROL_PORT}/",
        width=900,
        height=620,
    )

    def _on_closing():
        _window.hide()
        return False  # veto destroy; just hide to tray

    _window.events.closing += _on_closing
    webview.start()  # blocks on the main thread until the process exits


if __name__ == "__main__":
    main()
