"""Elevated entry point: generate + install the mitmproxy CA.

Run only via app.wizard.cert.install_cert_elevated() through a UAC prompt:
    python -m app.wizard._cert_admin
Reuses the existing MitmCertInstaller.
"""
from src.scripts.install_certificate import MitmCertInstaller


def main() -> int:
    installer = MitmCertInstaller()
    if not installer.generate_certificate():
        return 1
    return 0 if installer.install_certificate() else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
