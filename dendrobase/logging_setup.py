"""Налада логаў: кансоль + файл з ратацыяй у платформеннай папцы."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_HANDLER_TAG = "_dendrobase_handler"


def default_log_dir() -> Path:
    """Стандартная папка логаў для бягучай АС."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "DendroBASE" / "logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "DendroBASE"
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return base / "dendrobase" / "logs"


def _make_console_safe() -> None:
    """Каб кірыліца і іншыя сімвалы не валілі праграму на Windows-кансолі з cp1251."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def setup_logging(level: str = "INFO", log_dir: Path | None = None,
                  filename: str = "dendrobase.log") -> Path | None:
    """Наладзіць каранёвы логер. Вяртае шлях да файла логаў або None, калі файл стварыць не ўдалося.

    Паўторны выклік перазапісвае папярэднюю наладу (зручна ў тэстах).
    """
    _make_console_safe()
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_TAG, False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    setattr(console, _HANDLER_TAG, True)
    root.addHandler(console)

    directory = log_dir or default_log_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        file_handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        setattr(file_handler, _HANDLER_TAG, True)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("Не атрымалася стварыць файл логаў у %s: %s", directory, exc)
        return None

    root.debug("Логі пішуцца ў %s", path)
    return path
