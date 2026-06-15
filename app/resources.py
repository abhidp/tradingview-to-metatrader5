"""Resolve read-only bundled resources in both source and PyInstaller-frozen runs.

When frozen, PyInstaller extracts bundled data under sys._MEIPASS. In source runs
the same relative paths resolve under the repo root (the parent of this app/ dir).
"""
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Return the absolute path to a bundled resource given a repo-root-relative path."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent  # repo root (parent of app/)
    return base / rel
