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
from .logging_setup import setup_logging
from .ui.app import DendroApp
from .ui.feedback import install_exception_handler, show_error
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
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        _fatal("Памылка налад", str(exc))
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
            show_error("Несумяшчальная версія Tk", str(exc), parent=root)
        finally:
            root.destroy()
        return 2

    env_hint = " або ".join(str(path) for path in dotenv_candidates())
    try:
        db = DatabaseManager(settings.db)
        missing = db.check_schema()
    except ConnectionFailed as exc:
        show_error("Няма злучэння з базай даных",
                   f"{exc}\n\nПраверце, што сервер PostgreSQL запушчаны, і налады ў файле {env_hint}.", exc)
        root.destroy()
        return 1
    except DatabaseError as exc:
        show_error("Памылка базы даных", str(exc), exc)
        root.destroy()
        return 1
    if missing:
        show_error("У базе няма табліц",
                   f"У базе {settings.db.describe()} няма табліц: {', '.join(missing)}.\n\n"
                   "Выканайце schema.sql (гл. README, раздзел «Стварэнне табліц»).")
        db.close()
        root.destroy()
        return 1

    DendroApp(root, db, settings, log_path)
    root.deiconify()
    root.mainloop()
    db.close()
    log.info("Праграма завершана")
    return 0


if __name__ == "__main__":
    sys.exit(main())
