# tests/unit/test_cert_generate.py
from pathlib import Path

import src.scripts.install_certificate as ic


def test_generate_certificate_uses_certstore_not_mitmdump(monkeypatch, tmp_path):
    installer = ic.MitmCertInstaller()
    cert = tmp_path / ".mitmproxy" / "mitmproxy-ca-cert.cer"
    installer.cert_path = str(cert)

    calls = {}

    def fake_from_store(path, basename, key_size):
        calls["args"] = (Path(path), basename, key_size)
        Path(path).mkdir(parents=True, exist_ok=True)
        cert.write_text("CERT", encoding="utf-8")

    # Fail loudly if the old mitmdump subprocess path is taken.
    monkeypatch.setattr(ic.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("mitmdump used")))
    monkeypatch.setattr("mitmproxy.certs.CertStore.from_store", staticmethod(fake_from_store))

    assert installer.generate_certificate() is True
    assert cert.exists()
    assert calls["args"] == (cert.parent, "mitmproxy", 2048)
