"""Радок стану: апошняе паведамленне, бягучая ПП, падключэнне, PostGIS."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

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

    def notify(self, text: str, *, kind: str = "info", timeout_ms: int = 8000) -> None:
        """Паказаць паведамленне; інфармацыйныя знікаюць самі, памылкі застаюцца."""
        self.message.configure(text=f"{time.strftime('%H:%M')}  {text}", style=_STYLES.get(kind, "Status.TLabel"))
        if self._clear_after is not None:
            try:
                self.after_cancel(self._clear_after)
            except tk.TclError:
                pass
            self._clear_after = None
        if kind != "error" and timeout_ms > 0:
            self._clear_after = self.after(timeout_ms, lambda: self.message.configure(text=""))

    def set_probe(self, probe: str | None) -> None:
        self.probe.configure(text=f"ПП: {probe}" if probe else "")

    def set_postgis(self, available: bool) -> None:
        self.postgis.configure(text="PostGIS: ёсць" if available else "PostGIS: няма",
                               style="Ok.TLabel" if available else "Warn.TLabel")
