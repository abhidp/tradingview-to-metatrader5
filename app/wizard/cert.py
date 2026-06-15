"""Wizard step 2: mitmproxy CA certificate trust.

is_cert_trusted() is an idempotent check of the Windows Root store. Installing
the CA requires admin rights, so install_cert_elevated() launches a one-shot
elevated helper (app.wizard._cert_admin) via a UAC prompt; the app itself stays
unelevated. The frontend then polls is_cert_trusted() until it flips true.
"""
import subprocess
import sys

# mitmproxy's generated CA uses CN/issuer "mitmproxy". Pass the bare name as the
# certutil store filter, but confirm a match on the distinguished-name marker
# "CN=mitmproxy" — certutil echoes the bare search term in its header on some
# locales even with no match, which the substring check would misread as trusted.
_CERT_COMMON_NAME = "mitmproxy"
_CERT_TRUSTED_MARKER = "CN=mitmproxy"


def is_cert_trusted() -> bool:
    """True if the mitmproxy CA is already in the Windows Root store."""
    try:
        result = subprocess.run(
            ["certutil", "-store", "root", _CERT_COMMON_NAME],
            capture_output=True, text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and _CERT_TRUSTED_MARKER in (result.stdout or "")


def _launch_elevated_cert_install() -> int:
    """Trigger a UAC prompt to run the elevated cert-install helper.

    A frozen exe cannot run `-m module`, so it re-execs itself with the
    --run-cert-admin sentinel (handled in tv2mt5.py). From source we keep the
    module form. Returns the ShellExecuteW code (>32 means the launch was accepted).
    """
    import ctypes
    params = "--run-cert-admin" if getattr(sys, "frozen", False) else "-m app.wizard._cert_admin"
    return int(ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
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
