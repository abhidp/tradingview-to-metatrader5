# tests/unit/test_paths_data.py
from pathlib import Path

import app.paths as paths


def test_get_data_file_returns_appdata_data_subdir(tmp_path, monkeypatch):
    monkeypatch.setenv("TV2MT5_DATA_DIR", str(tmp_path))
    p = paths.get_data_file("symbol_mappings.json")
    assert p == tmp_path / "symbol_mappings.json"
    assert tmp_path.is_dir()  # dir created


def test_get_data_file_seeds_from_bundled_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TV2MT5_DATA_DIR", str(tmp_path))
    seed = tmp_path / "seed_src" / "instruments.json"
    seed.parent.mkdir(parents=True)
    seed.write_text('{"hello": 1}', encoding="utf-8")
    monkeypatch.setattr(paths, "resource_path", lambda rel: seed)

    p = paths.get_data_file("instruments.json", seed_name="instruments.json")
    assert p.read_text(encoding="utf-8") == '{"hello": 1}'


def test_get_data_file_no_seed_leaves_file_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("TV2MT5_DATA_DIR", str(tmp_path))
    p = paths.get_data_file("symbol_mappings.json")
    assert not p.exists()  # no seed_name -> caller initialises lazily
