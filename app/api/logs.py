"""Cursor-based tail of the rotating log file for the Logs view."""
from pathlib import Path
from typing import List, Tuple


def read_log_tail(path: Path, after: int = 0) -> Tuple[List[str], int]:
    """Return (new_lines, new_cursor) for bytes after the given offset.

    `after` is a byte offset into the file. If the file shrank (rotation), we
    restart from 0. Missing file returns ([], 0).
    """
    path = Path(path)
    if not path.exists():
        return [], 0
    size = path.stat().st_size
    if after > size:  # rotated/truncated
        after = 0
    if after == size:
        return [], size
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(after)
        text = fh.read()
    cursor = size
    lines = [ln for ln in text.splitlines() if ln != ""]
    return lines, cursor
