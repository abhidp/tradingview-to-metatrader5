import subprocess

from app.wizard import cert


class _R:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_is_cert_trusted_true(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _R(0, "== Certificate 0 ==\nIssuer: CN=mitmproxy\n"),
    )
    assert cert.is_cert_trusted() is True


def test_is_cert_trusted_false_when_absent(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R(0, "no certificates"))
    assert cert.is_cert_trusted() is False


def test_is_cert_trusted_false_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("certutil missing")
    monkeypatch.setattr(subprocess, "run", boom)
    assert cert.is_cert_trusted() is False


def test_install_returns_ok_when_already_trusted(monkeypatch):
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: True)
    assert cert.install_cert_elevated() == {"ok": True, "pending": False}


def test_install_pending_when_launch_accepted(monkeypatch):
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: False)
    monkeypatch.setattr(cert, "_launch_elevated_cert_install", lambda: 42)
    assert cert.install_cert_elevated() == {"ok": False, "pending": True}


def test_install_error_when_uac_declined(monkeypatch):
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: False)
    monkeypatch.setattr(cert, "_launch_elevated_cert_install", lambda: 5)
    r = cert.install_cert_elevated()
    assert r["ok"] is False
    assert r["pending"] is False
    assert "administrator" in r["error"]
