"""Радок стану: апошняе паведамленне, бягучая ПП, падключэнне, PostGIS."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ..i18n import tr
from .theme import PAD

_STYLES = {"info": "Status.TLabel", "ok": "Ok.TLabel", "warn": "Warn.TLabel", "error": "Error.TLabel"}


class StatusBar(ttk.Frame):
    def __init__(self, master: tk.Misc, *, connection: str = "", postgis: bool = False) -> None:
        super().__init__(master, padding=(PAD, 3))
        self.message = ttk.Label(self, text="", style="Status.TLabel", anchor="w")
        self.message.pack(side="left", fill="x", expand=True)
        self.postgis = ttk.Label(self, style="Status.TLabel")
        self.postgis.pack(side="right", padx=(PAD, 0))
        self.connection = ttk.Label(self, text=connection, style="Status.TLabel")
        self.connection.pack(side="right", padx=(PAD, 0))
        self.probe = ttk.Label(self, text="", style="Status.TLabel")
        self.probe.pack(side="right", padx=(PAD, 0))
        self.set_postgis(postgis)
        self._clear_after: str | None = None
        self._saved: tuple[str, str] | None = None
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _cancel_clear(self) -> None:
        if self._clear_after is not None:
            try:
                self.after_cancel(self._clear_after)
            except tk.TclError:
                pass
            self._clear_after = None

    def _on_destroy(self, event: tk.Event) -> None:
        # Радок стану перастаўляецца пры змене мовы або тэмы: адкладзеная ачыстка не павінна
        # звяртацца да ўжо знішчанага віджэта.
        if event.widget is self:
            self._cancel_clear()

    def notify(self, text: str, *, kind: str = "info", timeout_ms: int = 8000) -> None:
        """Паказаць паведамленне; інфармацыйныя знікаюць самі, памылкі застаюцца."""
        self._saved = None
        self.message.configure(text=f"{time.strftime('%H:%M')}  {text}", style=_STYLES.get(kind, "Status.TLabel"))
        self._cancel_clear()
        if kind != "error" and timeout_ms > 0:
            self._clear_after = self.after(timeout_ms, self._clear_message)

    def _clear_message(self) -> None:
        self._clear_after = None
        try:
            self.message.configure(text="")
        except tk.TclError:
            pass

    def show_hint(self, text: str | None) -> None:
        """Падказка пры навядзенні: часова замяняе паведамленне і вяртае яго пры выхадзе курсора."""
        if text:
            if self._saved is None:
                self._saved = (self.message.cget("text"), str(self.message.cget("style")))
            self.message.configure(text=text, style="Hint.TLabel")
        elif self._saved is not None:
            saved_text, saved_style = self._saved
            self._saved = None
            self.message.configure(text=saved_text, style=saved_style)

    def set_probe(self, probe: str | None) -> None:
        self.probe.configure(text=tr("ПП: {probe}").format(probe=probe) if probe else "")

    def set_postgis(self, available: bool) -> None:
        self.postgis.configure(text=tr("PostGIS: ёсць") if available else tr("PostGIS: няма"),
                               style="Ok.TLabel" if available else "Warn.TLabel")
