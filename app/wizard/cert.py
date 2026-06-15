"""Wizard step 2: mitmproxy CA certificate trust.

is_cert_trusted() is an idempotent check of the Windows Root store. Installing
the CA requires admin rights, so install_cert_elevated() launches a one-shot
elevated helper (app.wizard._cert_admin) via a UAC prompt; the app itself stays
unelevated. The frontend then polls is_cert_trusted() until it flips true.
"""
import subprocess
import sys

# mitmproxy's generated CA uses CN/issuer "mitmproxy".
_CERT_COMMON_NAME = "mitmproxy"


def is_cert_trusted() -> bool:
    """True if the mitmproxy CA is already in the Windows Root store."""
    try:
        result = subprocess.run(
            ["certutil", "-store", "root", _CERT_COMMON_NAME],
            capture_output=True, text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and _CERT_COMMON_NAME in (result.stdout or "")


def _launch_elevated_cert_install() -> int:
    """Trigger a UAC prompt to run the elevated cert-install helper.

    Returns the ShellExecuteW result code (>32 means the launch was accepted).
    """
    import ctypes
    return int(ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, "-m app.wizard._cert_admin", None, 1
    ))


def install_cert_elevated() -> dict:
    """Install the CA via an elevated helper. Idempotent.

    Returns one of:
      {"ok": True,  "pending": False}                already trusted
      {"ok": False, "pending": True}                 elevation launched; poll status
      {"ok": False, "pending": False, "error": ...}  UAC declined / launch failed
    """
    if is_cert_trusted():
        return {"ok": True, "pending": False}
    rc = _launch_elevated_cert_install()
    if rc <= 32:
        return {
            "ok": False, "pending": False,
            "error": "Could not get administrator access (was the UAC prompt declined?).",
        }
    return {"ok": False, "pending": True}
