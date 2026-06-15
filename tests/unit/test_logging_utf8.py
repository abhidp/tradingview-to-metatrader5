# tests/unit/test_logging_utf8.py
import sys

import app.logging_setup as ls


class _FakeStream:
    def __init__(self):
        self.reconfigured_with = None

    def reconfigure(self, **kwargs):
        self.reconfigured_with = kwargs


def test_force_utf8_streams_reconfigures_stdout_and_stderr(monkeypatch):
    out, err = _FakeStream(), _FakeStream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    ls._force_utf8_streams()
    assert out.reconfigured_with == {"encoding": "utf-8", "errors": "replace"}
    assert err.reconfigured_with == {"encoding": "utf-8", "errors": "replace"}


def test_force_utf8_streams_tolerates_none_streams(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ls._force_utf8_streams()  # must not raise


def test_force_utf8_streams_tolerates_non_reconfigurable(monkeypatch):
    class NoReconfig:
        pass
    monkeypatch.setattr(sys, "stdout", NoReconfig())
    monkeypatch.setattr(sys, "stderr", NoReconfig())
    ls._force_utf8_streams()  # must not raise (AttributeError swallowed)
