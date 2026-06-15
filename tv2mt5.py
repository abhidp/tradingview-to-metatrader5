# tv2mt5.py
"""Top-level entry for TV2MT5 Desktop (PyInstaller target).

Handles the elevated cert-admin re-exec first: a frozen exe cannot run
`python -m app.wizard._cert_admin`, so the elevated relaunch passes the
--run-cert-admin sentinel which we route here before any GUI/engine starts.
Otherwise launches the desktop app.
"""
import sys


def main() -> None:
    if "--run-cert-admin" in sys.argv:
        from app.wizard._cert_admin import main as cert_admin_main
        sys.exit(cert_admin_main())
    from app.desktop import main as desktop_main
    desktop_main()


if __name__ == "__main__":
    main()
