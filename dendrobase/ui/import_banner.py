"""Паласа над радком стану: «у папцы з Excel ёсць файлы для імпарту», кнопкі «Імпартаваць…» і «Схаваць».

Праверка папкі (import_state.pending_files) ідзе ў фонавым патоку: хэшаванне файлаў на павольным
або сеткавым дыску можа заняць секунды, а галоўнае акно павінна адкрыцца адразу. Паток не чапае Tk,
вынік забіраецца па таймеры (PendingImportCheck), як і ў акне імпарту.
"""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from ..i18n import tr
from ..import_state import PendingFiles, pending_files
from .theme import PAD, PALETTE, app_font, mix
from .widgets import add_tooltip

log = logging.getLogger("dendrobase.ui")
POLL_MS = 150


def describe_pending(pending: PendingFiles) -> str:
    """Радок для паласы: новыя файлы, змененыя або і тыя, і другія."""
    if not pending.changed:
        return tr("Знойдзены новыя Excel-файлы для імпарту: {count}.").format(count=len(pending.new))
    if not pending.new:
        return tr("Знойдзены змененыя Excel-файлы для імпарту: {count}.").format(count=len(pending.changed))
    return tr("Знойдзены Excel-файлы для імпарту: новых {new}, змененых {changed}.").format(
        new=len(pending.new), changed=len(pending.changed))


class ImportBanner(tk.Frame):
    """Паведамленне з кнопкамі; схаванае, пакуль show() не атрымае непусты PendingFiles.

    Класічны tk.Frame, а не ttk: яму можна задаць свой фон на ўсіх платформах. Колеры бяруцца з PALETTE
    бягучай тэмы, таму пры змене тэмы паласа ствараецца нанова разам з астатнім акном.
    """

    def __init__(self, master: tk.Misc, *, on_import: Callable[[], object], on_dismiss: Callable[[], None],
                 after_widget: tk.Misc | None = None) -> None:
        background = mix(PALETTE["table_bg"], PALETTE["accent"], 0.12)
        super().__init__(master, background=background, highlightthickness=0, borderwidth=0)
        self._after_widget = after_widget
        self.pending: PendingFiles | None = None

        tk.Frame(self, background=PALETTE["accent"], width=4, highlightthickness=0, borderwidth=0).pack(
            side="left", fill="y")
        body = tk.Frame(self, background=background, highlightthickness=0, borderwidth=0)
        body.pack(side="left", fill="x", expand=True, padx=PAD, pady=5)

        self.dismiss_button = ttk.Button(body, text=tr("Схаваць"), command=on_dismiss)
        self.dismiss_button.pack(side="right")
        add_tooltip(self.dismiss_button, tr("Паведамленне знікне да наступнага запуску праграмы або імпарту."))
        self.import_button = ttk.Button(body, text=tr("Імпартаваць…"), command=on_import)
        self.import_button.pack(side="right", padx=(0, 6))
        add_tooltip(self.import_button, tr("Ctrl+I. Адкрывае акно імпарту з гэтай папкай."))

        self.message = tk.Label(body, text="", background=background, foreground=PALETTE["text"],
                                font=app_font(bold=True), anchor="w")
        self.message.pack(side="left")
        add_tooltip(self.message, tr("Новыя: яшчэ не імпартаваліся. Змененыя: зменены пасля імпарту, "
                                     "скончыліся памылкай або іх ПП няма ў базе."))
        self.detail = tk.Label(body, text="", background=background, foreground=PALETTE["muted"], anchor="w")
        self.detail.pack(side="left", padx=(PAD, PAD))

    @property
    def visible(self) -> bool:
        return bool(self.winfo_manager())

    def show(self, pending: PendingFiles) -> None:
        self.pending = pending
        self.message.configure(text=describe_pending(pending))
        folder = Path(pending.folder)
        self.detail.configure(text=tr("Папка: {folder}").format(folder=folder.name or folder))
        add_tooltip(self.detail, str(folder))
        if not self.visible:
            options: dict[str, object] = {"side": "bottom", "fill": "x"}
            if self._after_widget is not None and self._after_widget.winfo_exists():
                options["after"] = self._after_widget
            self.pack(**options)

    def hide(self) -> None:
        self.pending = None
        if self.visible:
            self.pack_forget()


class PendingImportCheck:
    """Фонавая праверка папкі: pending_files() у патоку, вынік (або None пры памылцы) перадаецца on_done у патоку Tk.

    widget патрэбны толькі для таймера after; калі яго знішчылі раней, чым паток скончыў, вынік губляецца.
    """

    def __init__(self, widget: tk.Misc, folder: Path, probes: set[str],
                 on_done: Callable[[PendingFiles | None], None]) -> None:
        self.widget = widget
        self.folder = Path(folder)
        self.probes = set(probes)
        self.on_done = on_done
        self.result: PendingFiles | None = None
        self.finished = False
        self._after_id: str | None = None
        self._thread = threading.Thread(target=self._work, daemon=True, name="dendrobase-import-check")

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        log.debug("Праверка папкі з Excel-файламі: %s", self.folder)
        self._thread.start()
        self._schedule()

    def cancel(self) -> None:
        """Не перадаваць вынік: паток дапрацуе сам, але on_done не выклічацца."""
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _work(self) -> None:
        try:
            self.result = pending_files(self.folder, self.probes)
        except OSError as exc:
            log.warning("Папка з Excel-файламі %s не праверана: %s", self.folder, exc)

    def _schedule(self) -> None:
        self._after_id = self.widget.after(POLL_MS, self._poll)

    def _poll(self) -> None:
        self._after_id = None
        if self._thread.is_alive():
            self._schedule()
            return
        self.finished = True
        self.on_done(self.result)
