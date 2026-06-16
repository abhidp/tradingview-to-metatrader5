"""Desktop entrypoint: window (main thread) + API/engine loop (thread) + tray (thread).

Process model (Plan 3a):
- main thread runs the pywebview window (WebView2)
- a background thread runs one asyncio loop hosting uvicorn (FastAPI) + the engine
- a tray thread runs the pystray icon
Single-instance guard: bind the control port; if taken, focus the running app and exit.
"""
import asyncio
import ctypes
import logging
import os
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
_api_loop = None
_server = None
_controller = None
_tray = None
_quitting = False
_ctrl_handler_ref = None


def _quit() -> None:
    """Stop the engine cleanly, remove the tray icon, and terminate the process.

    Shared by tray Quit and the console Ctrl+C handler. The engine stop releases
    the proxy port + MT5 link gracefully; os._exit then guarantees termination
    (pywebview + WinForms/.NET + WebView2 keep the process alive after the window
    is destroyed, so a normal return would hang).
    """
    global _quitting
    if _quitting:  # guard against tray Quit and Ctrl+C racing
        return
    _quitting = True
    if _api_loop is not None and _api_loop.is_running() and _controller is not None:
        try:
            asyncio.run_coroutine_threadsafe(_controller.stop(), _api_loop).result(timeout=5.0)
        except Exception:
            pass
    if _tray is not None:
        try:
            _tray.stop()
        except Exception:
            pass
    os._exit(0)


def _install_console_ctrl_handler() -> None:
    """Make Ctrl+C / Ctrl+Break / console-close exit the app from the terminal.

    webview.start() blocks the main thread in native GUI code, so Python's SIGINT
    handler never runs. A Win32 console control handler runs on its own OS thread,
    so it fires regardless and drives the clean shutdown in _quit().
    """
    if os.name != "nt":
        return
    global _ctrl_handler_ref
    HANDLER = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

    def _on_ctrl(ctrl_type):  # 0=C_EVENT 1=BREAK 2=CLOSE 5=LOGOFF 6=SHUTDOWN
        _quit()
        return True

    _ctrl_handler_ref = HANDLER(_on_ctrl)  # keep a reference so it isn't GC'd
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler_ref, True)


def _configure_webview_env() -> None:
    """Disable WebView2 GPU acceleration by default.

    On some Windows GPU drivers, WebView2's hardware acceleration triggers a GPU
    hang / TDR that freezes the window, blanks the screen, and restarts DWM/Explorer
    (reproducible on window resize). The dashboard is lightweight text/lists, so
    software rendering is smooth and far safer across unknown machines. A user can
    override this by setting WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS themselves.
    """
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--disable-gpu")


def _run_api(controller: EngineController) -> None:
    """Run uvicorn (FastAPI + engine loop) on this thread's own asyncio loop.

    We manage the loop explicitly (rather than uvicorn's server.run()) so the
    main/tray thread can drive a clean engine shutdown via run_coroutine_threadsafe.
    """
    global _api_loop, _server
    try:
        _api_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_api_loop)
        app = create_app(controller, focus_callback=_focus_window, pick_file=_pick_terminal_file)
        config = uvicorn.Config(app, host=CONTROL_HOST, port=CONTROL_PORT, log_level="warning")
        _server = uvicorn.Server(config)
        _api_loop.run_until_complete(_server.serve())
    except Exception:
        logger.critical("API/engine thread crashed", exc_info=True)


def _focus_window() -> None:
    if _window is not None:
        try:
            _window.show()
            _window.restore()
        except Exception as e:  # noqa: BLE001
            logger.info("focus window failed: %s", e)


def _pick_terminal_file():
    """Open a native file dialog to choose terminal64.exe; return the path or None.

    pywebview marshals create_file_dialog to the GUI thread, so this is safe to call
    from the API worker thread. Returns None on cancel or if the window is gone.
    """
    if _window is None:
        return None
    try:
        result = _window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Executable (*.exe)", "All files (*.*)"),
        )
    except Exception as e:  # noqa: BLE001 - dialog failure must not crash the API
        logger.info("file dialog failed: %s", e)
        return None
    if not result:
        return None
    return result[0] if isinstance(result, (list, tuple)) else result


def main() -> None:
    global _window, _controller, _tray
    _configure_webview_env()
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

    _controller = EngineController()

    api_thread = threading.Thread(target=_run_api, args=(_controller,), daemon=True)
    api_thread.start()

    # Ctrl+C / Ctrl+Break in the launching terminal exits cleanly (see _quit).
    _install_console_ctrl_handler()

    _tray = build_tray(on_open=_focus_window, on_quit=lambda icon: _quit())
    tray_thread = threading.Thread(target=_tray.run, daemon=True)
    tray_thread.start()

    _window = webview.create_window(
        "TV2MT5 Desktop",
        f"http://{CONTROL_HOST}:{CONTROL_PORT}/",
        width=900,
        height=620,
        text_select=True,  # allow selecting/copying log + dashboard text (pywebview defaults to False)
    )

    def _on_closing():
        # Hide to tray instead of quitting. hide() must NOT run inline here: the
        # closing event fires on the GUI thread, and pywebview's hide() marshals
        # back to that same thread via Invoke(), which deadlocks ("not responding",
        # pywebview #1103). Running it from a background thread lets the marshal
        # complete once the GUI thread is free again.
        threading.Thread(target=_window.hide, daemon=True).start()
        return False  # veto the close; the background hide() minimises to tray

    _window.events.closing += _on_closing
    webview.start()  # blocks on the main thread until the process exits


if __name__ == "__main__":
    main()
