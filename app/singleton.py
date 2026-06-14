"""Single-instance guard for the desktop app.

The app binds one TCP port (CONTROL_PORT) that serves the UI + JSON API. That
bind is also the single-instance lock: if the port is already bound, another
instance is running. A second instance pings /api/focus on the first, then exits.
"""
import logging
import socket
from typing import Optional

logger = logging.getLogger("Singleton")

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8420


def acquire_single_instance(host: str = CONTROL_HOST, port: int = CONTROL_PORT) -> Optional[socket.socket]:
    """Bind and return the control socket, or None if already bound (another instance)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind((host, port))
        s.listen(128)
        s.setblocking(False)
        return s
    except OSError:
        s.close()
        return None


def is_another_instance_running(host: str = CONTROL_HOST, port: int = CONTROL_PORT) -> bool:
    """True if something is already accepting connections on the control port."""
    if port == 0:
        return False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def focus_running_instance(host: str = CONTROL_HOST, port: int = CONTROL_PORT) -> bool:
    """Best-effort: ask the running instance to raise its window via POST /api/focus."""
    try:
        import urllib.request

        req = urllib.request.Request(f"http://{host}:{port}/api/focus", method="POST")
        urllib.request.urlopen(req, timeout=1.0).close()
        return True
    except Exception as e:  # noqa: BLE001
        logger.info("focus request failed: %s", e)
        return False
