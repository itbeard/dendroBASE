"""Паведамленні карыстальніку. Кожнае паведамленне адначасова трапляе ў лог."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

log = logging.getLogger("dendrobase.ui")


def show_error(title: str, message: str, exc: BaseException | None = None, parent: tk.Misc | None = None) -> None:
    if exc is not None:
        log.error("%s: %s", title, message, exc_info=exc)
    else:
        log.error("%s: %s", title, message)
    messagebox.showerror(title, message, parent=parent)


def show_warning(title: str, message: str, parent: tk.Misc | None = None) -> None:
    log.warning("%s: %s", title, message)
    messagebox.showwarning(title, message, parent=parent)


def show_info(title: str, message: str, parent: tk.Misc | None = None) -> None:
    log.info("%s: %s", title, message)
    messagebox.showinfo(title, message, parent=parent)


def ask_yes_no(title: str, message: str, parent: tk.Misc | None = None) -> bool:
    answer = bool(messagebox.askyesno(title, message, parent=parent))
    log.info("%s: %s -> %s", title, message, "так" if answer else "не")
    return answer


def ask_yes_no_cancel(title: str, message: str, parent: tk.Misc | None = None) -> bool | None:
    """Так / Не / Адмена. Вяртае True, False або None (адмена)."""
    answer = messagebox.askyesnocancel(title, message, parent=parent)
    log.info("%s: %s -> %s", title, message, {True: "так", False: "не", None: "адмена"}[answer])
    return answer


def install_exception_handler(root: tk.Tk) -> None:
    """Неапрацаваныя выключэнні ў апрацоўшчыках Tk ідуць у лог і ў акно, а не ў stderr."""

    def handler(exc_type, exc_value, traceback) -> None:
        log.error("Неапрацаваная памылка ў інтэрфейсе", exc_info=(exc_type, exc_value, traceback))
        try:
            messagebox.showerror(
                "Нечаканая памылка",
                f"{exc_type.__name__}: {exc_value}\n\nПадрабязнасці запісаны ў файл логаў.",
            )
        except tk.TclError:
            pass

    root.report_callback_exception = handler  # type: ignore[method-assign]
