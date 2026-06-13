"""`python -m app` — launch the single-process TV2MT5 engine."""
import asyncio
import sys

from app.engine import run_engine
from app.logging_setup import setup_logging


def _force_utf8_console() -> None:
    """Make stdout/stderr UTF-8.

    The app logs emoji status lines. Windows consoles (and any redirected/
    piped stdout, including the future packaged .exe) default to cp1252, which
    raises UnicodeEncodeError on those characters. Reconfiguring to UTF-8 with
    errors='replace' makes logging safe regardless of the host code page.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # non-reconfigurable stream (e.g. already wrapped) — best effort


_force_utf8_console()
setup_logging()


def main() -> None:
    try:
        asyncio.run(run_engine())
    except KeyboardInterrupt:
        print("\n⛔ Shutdown requested...")


if __name__ == "__main__":
    main()
