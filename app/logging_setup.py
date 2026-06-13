"""Console + rotating-file logging for the TV2MT5 app.

Captures BOTH logging records and raw print()/stderr output into a rotating
log file under <app data dir>/logs/, while still echoing to the console.
The codebase uses many print() calls for trade events; teeing stdout/stderr
through a file-only mirror logger captures them without rewriting those calls.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.paths import get_data_dir

_configured = False


def get_log_dir() -> Path:
    """Return (and create) the directory holding log files."""
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


class _StreamTee:
    """Write to the real stream AND mirror complete lines to a logger.

    The mirror logger writes only to the file handler (propagate=False), and
    the root logger's console handler targets the REAL stream (captured before
    teeing), so stdout capture never recurses with logging's console output.
    """

    def __init__(self, real_stream, mirror_logger, level):
        self._real = real_stream
        self._logger = mirror_logger
        self._level = level
        self._buf = ""

    def write(self, s):
        self._real.write(s)
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._logger.log(self._level, line)

    def flush(self):
        self._real.flush()

    def isatty(self):
        return getattr(self._real, "isatty", lambda: False)()

    def fileno(self):
        return self._real.fileno()


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure root logging (console + rotating file) and tee stdout/stderr.

    Idempotent. Returns the log file path.
    """
    global _configured
    log_file = get_log_dir() / "tv2mt5.log"
    if _configured:
        return log_file

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    # Capture the REAL console streams before teeing so logging's console
    # handler writes to them directly (never into the tee → no recursion).
    real_stdout = sys.stdout
    real_stderr = sys.stderr

    console_handler = logging.StreamHandler(real_stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Mirror logger for teed print()/stderr: file only, no propagation.
    mirror = logging.getLogger("app.console_capture")
    mirror.setLevel(level)
    mirror.propagate = False
    mirror.handlers.clear()
    mirror.addHandler(file_handler)

    sys.stdout = _StreamTee(real_stdout, mirror, logging.INFO)
    sys.stderr = _StreamTee(real_stderr, mirror, logging.ERROR)

    _configured = True
    logging.getLogger("Engine").info("Logging to %s", log_file)
    return log_file
