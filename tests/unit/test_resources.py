import sys
from pathlib import Path

from app.resources import resource_path


def test_resource_path_from_source_points_at_repo_root():
    # In source mode (sys.frozen unset), app/ui must resolve under the repo root.
    p = resource_path("app/ui")
    assert p.name == "ui"
    assert (p.parent.name == "app")
    assert (p.parent.parent / "app").is_dir()


def test_resource_path_uses_meipass_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    p = resource_path("data/instruments.json")
    assert p == Path(tmp_path) / "data" / "instruments.json"
