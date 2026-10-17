"""Кропка ўваходу: python -m dendrobase"""
from __future__ import annotations

import logging
import platform
import sys
import tkinter as tk
from tkinter import messagebox

from . import __version__
from .config import ConfigError, Settings, dotenv_candidates
from .db import ConnectionFailed, DatabaseError, DatabaseManager
from .i18n import set_language, tr
from .logging_setup import setup_logging
from .ui.app import DendroApp
from .ui.feedback import install_exception_handler, show_error
from .ui.preferences import load_preferences
from .ui.runtime import UnsupportedTkError, check_tk_runtime

log = logging.getLogger("dendrobase")


def enable_high_dpi() -> None:
    """На Windows без гэтага інтэрфейс размыты на экранах з маштабаваннем."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - старыя версіі Windows
        pass


def _fatal(title: str, message: str) -> None:
    print(f"{title}: {message}", file=sys.stderr)
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except tk.TclError:
        pass


def main(argv: list[str] | None = None) -> int:
    preferences = load_preferences()  # мова патрэбна ўжо для першых паведамленняў пра памылкі
    set_language(preferences.language)
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        _fatal(tr("Памылка налад"), str(exc))
        return 2

    log_path = setup_logging(settings.log_level, settings.log_dir)
    log.info("DendroBASE %s, Python %s, %s", __version__, platform.python_version(), platform.platform())
    enable_high_dpi()

    root = tk.Tk()
    root.withdraw()
    install_exception_handler(root)
    try:
        check_tk_runtime(root)
    except UnsupportedTkError as exc:
        try:
            show_error(tr("Несумяшчальная версія Tk"), str(exc), parent=root)
        finally:
            root.destroy()
        return 2

    env_hint = tr(" або ").join(str(path) for path in dotenv_candidates())
    try:
        db = DatabaseManager(settings.db)
        missing = db.check_schema()
    except ConnectionFailed as exc:
        show_error(tr("Няма злучэння з базай даных"),
                   tr("{error}\n\nПраверце, што сервер PostgreSQL запушчаны, і налады ў файле {env}.")
                   .format(error=exc, env=env_hint), exc)
        root.destroy()
        return 1
    except DatabaseError as exc:
        show_error(tr("Памылка базы даных"), str(exc), exc)
        root.destroy()
        return 1
    if missing:
        show_error(tr("У базе няма табліц"),
                   tr("У базе {db} няма табліц: {tables}.\n\nВыканайце schema.sql (гл. README, раздзел «Стварэнне табліц»).")
                   .format(db=settings.db.describe(), tables=", ".join(missing)))
        db.close()
        root.destroy()
        return 1

    DendroApp(root, db, settings, log_path, preferences)
    root.deiconify()
    root.mainloop()
    db.close()
    log.info("Праграма завершана")
    return 0


if __name__ == "__main__":
    sys.exit(main())
