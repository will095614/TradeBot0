"""src/logging_setup.py - Root logging configuration for TradeBot0.

Audit 3.10: the release build is windowed (PyInstaller ``console=False``),
so ``sys.stdout``/``sys.stderr`` are None and a bare ``StreamHandler`` discards
every log record. This module configures a rotating file handler so the
shipped exe always leaves a diagnostic record, and keeps the console stream
handler only when a real stdout exists.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_FILENAME = "tradebot0.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_LEVEL = logging.INFO
# 5 MB per file, 5 backups: ~30 MB ceiling, small enough for any install.
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5


def get_log_dir() -> Path:
    """Resolve the log directory with the same rule the app uses for its data dir.

    Frozen (installed exe): ``%APPDATA%\\TradeBot0\\logs`` (``~/.tradebot0/logs``
    when APPDATA is missing). Source checkout: ``<project>/data/logs``.
    Mirrors ConfigManager (src/intelligence/config_manager.py) and
    ArenaStorage (src/data/persistence.py) path resolution.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
        return base / "logs"
    return Path(__file__).resolve().parent.parent / "data" / "logs"


def configure_logging(log_dir: Optional[Path] = None) -> Path:
    """Configure the root logger. Returns the log directory actually used.

    Always attaches a RotatingFileHandler (created under ``log_dir``);
    attaches a StreamHandler only when ``sys.stdout`` is not None (a
    windowed PyInstaller build has stdout == None). Never raises: if the
    log directory cannot be created or the file cannot be opened, startup
    must continue with whatever handlers could be attached. Re-runnable
    (``force=True``) so tests can reconfigure it.
    """
    resolved = Path(log_dir) if log_dir is not None else get_log_dir()
    handlers: list = []
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            resolved / LOG_FILENAME,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handlers.append(file_handler)
    except Exception:
        # No file logging possible (read-only dir, etc.): keep going with
        # the stream handler if one exists; logging must never kill startup.
        pass
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, handlers=handlers, force=True)
    logging.getLogger("TradeBot0").info("Logging to %s", resolved / LOG_FILENAME)
    return resolved
