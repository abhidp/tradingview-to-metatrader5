"""Regression guard: the desktop app must disable WebView2 GPU acceleration
by default (a GPU hang/TDR on some Windows drivers froze the window and
restarted Explorer on resize), while respecting a user override.
"""
import os


def test_configure_webview_env_disables_gpu_by_default(monkeypatch):
    monkeypatch.delenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", raising=False)
    from app.desktop import _configure_webview_env

    _configure_webview_env()
    assert "--disable-gpu" in os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]


def test_configure_webview_env_respects_user_override(monkeypatch):
    monkeypatch.setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--my-flag")
    from app.desktop import _configure_webview_env

    _configure_webview_env()
    assert os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--my-flag"
