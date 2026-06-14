"""run.py must launch the single-process/desktop apps with the project's venv
interpreter (which has the app deps), so `python run.py desktop` works even when
invoked with a bare system Python that lacks pywebview/mitmproxy/etc.
"""
import sys
from pathlib import Path

from run import Runner


def test_resolve_python_prefers_windows_venv(tmp_path):
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    py = scripts / "python.exe"
    py.write_text("")
    assert Runner._resolve_python(tmp_path) == str(py)


def test_resolve_python_prefers_posix_venv(tmp_path):
    bind = tmp_path / "venv" / "bin"
    bind.mkdir(parents=True)
    py = bind / "python"
    py.write_text("")
    assert Runner._resolve_python(tmp_path) == str(py)


def test_resolve_python_falls_back_to_sys_executable(tmp_path):
    # No venv under tmp_path -> use the current interpreter.
    assert Runner._resolve_python(tmp_path) == sys.executable
