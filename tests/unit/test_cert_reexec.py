# tests/unit/test_cert_reexec.py
import sys

import app.wizard.cert as cert


class _FakeShell:
    def __init__(self):
        self.last = None

    def ShellExecuteW(self, hwnd, verb, file, params, directory, show):
        self.last = (verb, file, params)
        return 42  # >32 == accepted


def _patch_shell(monkeypatch):
    fake = _FakeShell()
    import ctypes
    monkeypatch.setattr(ctypes, "windll", type("W", (), {"shell32": fake}), raising=False)
    return fake


def test_reexec_uses_module_flag_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    fake = _patch_shell(monkeypatch)
    cert._launch_elevated_cert_install()
    assert fake.last[2] == "-m app.wizard._cert_admin"


def test_reexec_uses_argv_sentinel_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    fake = _patch_shell(monkeypatch)
    cert._launch_elevated_cert_install()
    assert fake.last[2] == "--run-cert-admin"
