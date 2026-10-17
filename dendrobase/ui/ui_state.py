"""Запамінанне стану інтэрфейсу паміж запускамі: памер акна, раздзяляльнік, апошняя ПП."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..paths import app_data_dir

log = logging.getLogger(__name__)
STATE_FILE = app_data_dir() / "ui_state.json"


def load_ui_state(path: Path | None = None) -> dict:
    path = path or STATE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.debug("Стан інтэрфейсу не прачытаны (%s): %s", path, exc)
        return {}


def save_ui_state(update: dict, path: Path | None = None) -> None:
    path = path or STATE_FILE
    state = load_ui_state(path)
    state.update(update)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.debug("Стан інтэрфейсу не захаваны (%s): %s", path, exc)
