"""Платформенныя папкі праграмы: даныя інтэрфейсу і логі."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "DendroBASE"


def app_data_dir() -> Path:
    """Папка для стану інтэрфейсу і іншых дробных файлаў карыстальніка."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return base / APP_NAME.lower()


def default_log_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    return app_data_dir() / "logs"
