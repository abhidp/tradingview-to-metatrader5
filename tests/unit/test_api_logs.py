from app.api.logs import read_log_tail


def test_read_from_start_returns_all_then_advances(tmp_path):
    f = tmp_path / "app.log"
    f.write_text("line1\nline2\n", encoding="utf-8")

    lines, cursor = read_log_tail(f, after=0)
    assert lines == ["line1", "line2"]
    assert cursor == f.stat().st_size

    lines2, cursor2 = read_log_tail(f, after=cursor)
    assert lines2 == []
    assert cursor2 == cursor

    with f.open("a", encoding="utf-8") as fh:
        fh.write("line3\n")
    lines3, cursor3 = read_log_tail(f, after=cursor)
    assert lines3 == ["line3"]
    assert cursor3 == f.stat().st_size


def test_missing_file_is_empty(tmp_path):
    lines, cursor = read_log_tail(tmp_path / "nope.log", after=0)
    assert lines == []
    assert cursor == 0
