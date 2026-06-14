"""System-tray icon (pystray): Start / Stop / Open / Quit. Talks to the local API."""
import logging
import urllib.request

from PIL import Image, ImageDraw
import pystray

from app.singleton import CONTROL_HOST, CONTROL_PORT

logger = logging.getLogger("Tray")


def _api(path: str, method: str = "POST") -> None:
    try:
        req = urllib.request.Request(
            f"http://{CONTROL_HOST}:{CONTROL_PORT}{path}", method=method
        )
        urllib.request.urlopen(req, timeout=2.0).close()
    except Exception as e:  # noqa: BLE001
        logger.info("tray api %s failed: %s", path, e)


def _icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), "#1f2430")
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, 46, 46], fill="#2d6cdf")
    return img


def build_tray(on_open, on_quit) -> "pystray.Icon":
    """Build (but do not run) the tray icon. on_open/on_quit are callables."""
    menu = pystray.Menu(
        pystray.MenuItem("Open", lambda icon, item: on_open()),
        pystray.MenuItem("Start", lambda icon, item: _api("/api/engine/start")),
        pystray.MenuItem("Stop", lambda icon, item: _api("/api/engine/stop")),
        pystray.MenuItem("Quit", lambda icon, item: on_quit(icon)),
    )
    return pystray.Icon("tv2mt5", _icon_image(), "TV2MT5", menu)
