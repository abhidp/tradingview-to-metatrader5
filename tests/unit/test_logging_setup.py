import logging

import app.logging_setup as logging_setup


def test_setup_logging_writes_console_and_print_to_file(temp_db_path, capsys):
    import sys
    real_out, real_err = sys.stdout, sys.stderr
    try:
        logging_setup._configured = False
        log_file = logging_setup.setup_logging()

        logging.getLogger("test.logger").info("hello-from-logging")
        print("hello-from-print")

        # flush handlers
        for h in logging.getLogger().handlers:
            h.flush()
        for h in logging.getLogger("app.console_capture").handlers:
            h.flush()

        contents = log_file.read_text(encoding="utf-8")
        assert "hello-from-logging" in contents
        assert "hello-from-print" in contents
    finally:
        # restore global state so other tests aren't affected
        sys.stdout, sys.stderr = real_out, real_err
        root = logging.getLogger()
        for h in list(root.handlers):
            h.close()
            root.removeHandler(h)
        mirror = logging.getLogger("app.console_capture")
        for h in list(mirror.handlers):
            h.close()
            mirror.removeHandler(h)
        logging_setup._configured = False


def test_connection_reset_records_are_dropped_others_kept():
    """The noise filter drops ConnectionResetError records, keeps real ones."""
    import sys
    import logging as _logging
    from app.logging_setup import _DropConnectionResetNoise

    f = _DropConnectionResetNoise()

    try:
        raise ConnectionResetError(10054, "forcibly closed")
    except ConnectionResetError:
        reset_rec = _logging.LogRecord(
            "mitmproxy.master", _logging.ERROR, __file__, 1,
            "Unhandled error in task.", None, sys.exc_info()
        )
    assert f.filter(reset_rec) is False

    try:
        raise ValueError("a real error")
    except ValueError:
        real_rec = _logging.LogRecord(
            "x", _logging.ERROR, __file__, 1, "boom", None, sys.exc_info()
        )
    assert f.filter(real_rec) is True

    # records with no exception pass through
    plain = _logging.LogRecord("x", _logging.INFO, __file__, 1, "hello", None, None)
    assert f.filter(plain) is True
