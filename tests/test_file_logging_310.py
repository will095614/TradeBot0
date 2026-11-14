"""Audit 3.10 regression tests: the release build must write a log file.

The shipped exe is windowed (PyInstaller console=False), so sys.stdout and
sys.stderr are None and the old StreamHandler(sys.stdout) setup discarded
every log record. configure_logging always attaches a RotatingFileHandler
and keeps the stream handler only when a real stdout exists.

All tests point the log dir at tmp_path; none touches the real %APPDATA%
or the project data dir.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from src.logging_setup import (
    LOG_BACKUP_COUNT,
    LOG_FILENAME,
    LOG_MAX_BYTES,
    configure_logging,
    get_log_dir,
)


@pytest.fixture(autouse=True)
def _remove_test_handlers():
    before = list(logging.root.handlers)
    yield
    for h in list(logging.root.handlers):
        if h not in before:
            logging.root.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass


def _flush_file_handlers():
    for h in logging.root.handlers:
        if isinstance(h, logging.FileHandler):
            h.flush()


def test_windowed_mode_writes_log_file(tmp_path, monkeypatch):
    """sys.stdout/sys.stderr None (windowed build): records still land in the file."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    log_dir = tmp_path / "logs"
    configure_logging(log_dir=log_dir)
    logger = logging.getLogger("TradeBot0.test")
    logger.info("windowed info record")
    logger.error("windowed error record")
    _flush_file_handlers()
    log_file = log_dir / LOG_FILENAME
    assert log_file.exists()
    text = log_file.read_text(encoding="utf-8")
    assert "windowed info record" in text
    assert "windowed error record" in text


def test_stream_handler_skipped_when_stdout_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    configure_logging(log_dir=tmp_path / "logs")
    handlers = logging.root.handlers
    # Exact type: pytest's own LogCaptureHandler is a StreamHandler subclass
    # and must not be mistaken for our console handler.
    assert not any(type(h) is logging.StreamHandler for h in handlers)
    file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].maxBytes == LOG_MAX_BYTES
    assert file_handlers[0].backupCount == LOG_BACKUP_COUNT


def test_stream_handler_present_when_stdout_exists(tmp_path):
    assert sys.stdout is not None
    configure_logging(log_dir=tmp_path / "logs")
    handlers = logging.root.handlers
    assert any(type(h) is logging.StreamHandler for h in handlers)
    assert any(isinstance(h, RotatingFileHandler) for h in handlers)


def test_get_log_dir_resolution(tmp_path, monkeypatch):
    # Frozen exe with APPDATA.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    assert get_log_dir() == tmp_path / "AppData" / "TradeBot0" / "logs"
    # Frozen exe without APPDATA.
    monkeypatch.delenv("APPDATA")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert get_log_dir() == tmp_path / "home" / ".tradebot0" / "logs"
    # Source checkout.
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert get_log_dir() == Path(__file__).resolve().parent.parent / "data" / "logs"


def test_configure_logging_never_raises_on_unwritable_dir(tmp_path, monkeypatch):
    """A read-only/unwritable log dir must not kill startup."""
    # Point at a path whose parent is a FILE, so mkdir must fail.
    not_a_dir = tmp_path / "file-not-dir"
    not_a_dir.write_text("x", encoding="utf-8")
    returned = configure_logging(log_dir=not_a_dir / "logs")
    assert returned == not_a_dir / "logs"


def test_main_py_uses_file_logging():
    text = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
    assert "configure_logging" in text
    assert "StreamHandler(sys.stdout)" not in text
