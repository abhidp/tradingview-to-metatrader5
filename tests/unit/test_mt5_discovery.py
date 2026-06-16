# tests/unit/test_mt5_discovery.py
import src.services.mt5_service as mod


def _make_terminal(root, *parts):
    p = root.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")
    return p


def test_discover_scans_multiple_roots_drops_name_filter_and_dedupes(tmp_path, monkeypatch):
    appdata = tmp_path / "Roaming"
    progfiles = tmp_path / "ProgramFiles"
    # A broker WITHOUT "MT5" in the name (old filter would have missed it):
    vantage = _make_terminal(progfiles, "Vantage Australia Terminal", "terminal64.exe")
    fusion = _make_terminal(appdata, "Fusion Markets MT5 Terminal", "terminal64.exe")

    monkeypatch.setattr(mod, "_terminal_roots",
                        lambda: [appdata, progfiles, tmp_path / "missing"])
    monkeypatch.setattr(mod, "_running_terminal_paths", lambda: [str(fusion)])  # dupe of fusion

    found = mod.discover_mt5_terminals()
    paths = sorted(t["path"].lower() for t in found)
    assert str(vantage).lower() in paths
    assert str(fusion).lower() in paths
    # Fusion appears via both filesystem and running-process — must be deduped.
    assert paths.count(str(fusion).lower()) == 1


def test_discover_labels_from_parent_folder(tmp_path, monkeypatch):
    pf = tmp_path / "PF"
    _make_terminal(pf, "Fusion Markets MT5 Terminal", "terminal64.exe")
    monkeypatch.setattr(mod, "_terminal_roots", lambda: [pf])
    monkeypatch.setattr(mod, "_running_terminal_paths", lambda: [])
    [t] = mod.discover_mt5_terminals()
    assert t["label"] == "Fusion Markets"  # " MT5 Terminal" suffix stripped


def test_scan_root_respects_max_depth(tmp_path):
    # _scan_root uses default max_depth=3 and stops descending once the dir
    # depth (relative to root) reaches max_depth. A terminal whose parent dir
    # is at depth 1 is found; one whose parent dir is at depth 6 is excluded.
    shallow = _make_terminal(tmp_path, "Broker", "terminal64.exe")
    _make_terminal(tmp_path, "a", "b", "c", "d", "DeepBroker", "terminal64.exe")
    found = [p.lower() for p in mod._scan_root(tmp_path)]
    assert str(shallow).lower() in found
    assert not any("deepbroker" in p for p in found)


def test_find_mt5_terminals_is_path_list(tmp_path, monkeypatch):
    pf = tmp_path / "PF"
    _make_terminal(pf, "MetaTrader 5", "terminal64.exe")
    monkeypatch.setattr(mod, "_terminal_roots", lambda: [pf])
    monkeypatch.setattr(mod, "_running_terminal_paths", lambda: [])
    paths = mod.find_mt5_terminals()
    assert isinstance(paths, list) and all(isinstance(p, str) for p in paths)
    assert len(paths) == 1
