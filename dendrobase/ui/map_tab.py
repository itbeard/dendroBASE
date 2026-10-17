"""Укладка «Карта храналогій»: спіс ПП з каардынатамі і карта folium у браўзеры."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..maps import build_map, open_in_browser, save_map, temp_map_path
from .feedback import show_error, show_info
from .theme import PAD
from .widgets import add_tooltip, fill_tree, make_treeview

Notify = Callable[..., None]


class MapTab:
    def __init__(self, notebook: ttk.Notebook, db: DatabaseManager, notify: Notify | None = None,
                 on_pick: Callable[[str], None] | None = None) -> None:
        self.db = db
        self.notify: Notify = notify or (lambda text, **kwargs: None)
        self.on_pick = on_pick
        self.frame = ttk.Frame(notebook, padding=(PAD, PAD, PAD, 0))

        header = ttk.Frame(self.frame)
        header.pack(fill="x")
        ttk.Label(header, text="Карта храналогій", style="Heading.TLabel").pack(side="left")
        self.status = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.status.pack(side="left", padx=(PAD * 2, 0))

        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill="x", pady=(6, 4))
        open_button = ttk.Button(toolbar, text="Адкрыць карту ў браўзеры", command=self.open_map)
        open_button.pack(side="left")
        add_tooltip(open_button, "Інтэрактыўная карта (падкладка OpenTopoMap на даных OpenStreetMap) з маркерамі ўсіх ПП, якія маюць каардынаты.")
        ttk.Button(toolbar, text="Захаваць як HTML…", command=self.save_as).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Абнавіць спіс", command=self.refresh).pack(side="left", padx=4)
        ttk.Label(self.frame, style="Hint.TLabel", wraplength=900, justify="left",
                  text="Ніжэй толькі ПП з каардынатамі. Падвойны клік адкрывае ПП. "
                       "Каардынаты ўводзяцца на ўкладцы «Інфармацыя аб ПП» у дзесятковых градусах.").pack(anchor="w")

        self.tree = make_treeview(self.frame, ("Код", "Парода", "Шырата", "Даўгата", "Гады"),
                                  numeric={"Шырата": 4, "Даўгата": 4}, horizontal=False, selectmode="browse")
        self.tree.column("Код", width=140)
        self.tree.column("Парода", width=80)
        self.tree.column("Гады", width=100)
        self.tree.master.pack(fill="both", expand=True, pady=(6, PAD))
        self.tree.bind("<Double-1>", self._on_double_click)

    def refresh(self) -> None:
        try:
            summaries = self.db.list_probes()
            points = {point.name: point for point in self.db.get_probe_points()}
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць каардынаты:\n{exc}", exc)
            return
        rows = [
            (point.name, point.poroda or "", point.lat, point.lon,
             f"{point.first_year or '?'}–{point.last_year or '?'}" if point.first_year or point.last_year else "")
            for point in points.values()
        ]
        self.tree.delete(*self.tree.get_children())
        fill_tree(self.tree, rows)
        self.status.configure(text=f"ПП з каардынатамі: {len(points)} з {len(summaries)}")

    def _on_double_click(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if selected and self.on_pick:
            self.on_pick(str(self.tree.item(selected[0], "values")[0]))

    def _build(self):
        try:
            points = self.db.get_probe_points()
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася прачытаць каардынаты:\n{exc}", exc)
            return None, 0
        if not points:
            self.notify("Няма пробных плошчаў з каардынатамі.", kind="warn")
            return None, 0
        return build_map(points), len(points)

    def open_map(self) -> None:
        fmap, count = self._build()
        if fmap is None:
            return
        try:
            path = save_map(fmap, temp_map_path())
            opened = open_in_browser(path)
        except OSError as exc:
            show_error("Памылка", f"Не атрымалася стварыць карту:\n{exc}", exc)
            return
        if opened:
            self.notify(f"Карта з {count} ПП адкрыта ў браўзеры.", kind="ok")
        else:
            show_info("Карта захавана", f"Браўзер не адкрыўся. Адкрыйце файл уручную:\n{path}")

    def save_as(self) -> None:
        target = filedialog.asksaveasfilename(
            title="Захаваць карту", defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("Усе файлы", "*.*")], initialfile="dendrobase_map.html",
        )
        if not target:
            return
        fmap, count = self._build()
        if fmap is None:
            return
        try:
            save_map(fmap, Path(target))
        except OSError as exc:
            show_error("Памылка", f"Не атрымалася захаваць карту:\n{exc}", exc)
            return
        self.notify(f"Карта з {count} ПП захавана: {target}", kind="ok")
